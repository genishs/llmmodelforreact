# -*- coding: utf-8 -*-
"""
로컬 GPU 직접 학습 스크립트 — LoRA fine-tuning. (DirectML / ROCm·CUDA 이중 백엔드)

기존 train.py는 CPU 전용(통합 16GB VRAM 시절 작성). 이 스크립트는:
  1) 모델을 meta(빈 가중치)로 만든 뒤 safetensors 텐서를 하나씩 변환해 GPU에 직접
     적재(host RAM 피크 = 가장 큰 텐서 1개분 → 호스트 RAM 적어도 29GB+ 적재 가능).
  2) HF Trainer 대신 백엔드 인지 커스텀 학습 루프.
  3) **--backend로 directml(Windows 기본) / cuda(ROCm·CUDA) 전환.** cuda는 empty_cache로
     단편화를 해소해 더 높은 seq가 가능하고, bf16·PYTORCH_CUDA_ALLOC_CONF가 작동.
     (DirectML은 empty_cache 부재로 14B fp16이 seq256에 막힘 — ROCm 전환의 동기.)

실행:
  python src/train_directml.py --smoke 2                       # DirectML 스모크
  python src/train_directml.py --backend cuda --dtype bf16 ... # ROCm/CUDA 본런(고seq)
"""

import os
import sys
import io
import time
import glob
import json
import signal
import argparse
import datetime as dt

import yaml
import torch
import psutil

# Windows 콘솔 UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", line_buffering=True)

from transformers import (
    AutoConfig,
    AutoModelForCausalLM,
    AutoTokenizer,
    DataCollatorForLanguageModeling,
    get_cosine_schedule_with_warmup,
)
from datasets import load_dataset
from peft import LoraConfig, get_peft_model, TaskType
from accelerate import init_empty_weights
from accelerate.utils import set_module_tensor_to_device
from safetensors import safe_open
from torch.utils.data import DataLoader

RAM_GUARD_GB = 0.5  # 로딩 중 가용 RAM이 이 밑으로 떨어지면 중단(프리징 방지)


def log(msg):
    ts = dt.datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def ram_avail_gb():
    return psutil.virtual_memory().available / 1024**3


def resolve_backend(name):
    """백엔드 추상화 → (backend, device, device_name, empty_cache_fn, mem_used_gb_fn).

    - directml: torch_directml(이 디바이스 Windows 기본). empty_cache 없음(no-op),
      메모리 측정 불안정. bf16 미지원·fp16 강제.
    - cuda: ROCm/HIP(또는 NVIDIA). **torch.cuda.empty_cache 작동 → 단편화 해소로 고seq 가능**,
      bf16 지원, PYTORCH_CUDA_ALLOC_CONF 등 env var 유효. gfx1151 TheRock(Windows) / Linux ROCm.
    """
    if name == "auto":
        name = "cuda" if torch.cuda.is_available() else "directml"
    if name == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("--backend cuda인데 torch.cuda.is_available()=False "
                               "(ROCm/CUDA 휠 미설치). TheRock gfx1151 또는 Linux ROCm 필요.")
        dev = torch.device("cuda")
        dn = torch.cuda.get_device_name(0)
        return ("cuda", dev, dn,
                lambda: torch.cuda.empty_cache(),
                lambda: torch.cuda.memory_allocated() / 1024**3)
    # directml
    import torch_directml
    dev = torch_directml.device()
    dn = torch_directml.device_name(0)
    return ("directml", dev, dn, (lambda: None), (lambda: float("nan")))


def load_config(path="./config/training_config.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def stream_load_to_device(model_path, device, dtype):
    """safetensors 텐서를 지정 dtype으로 변환해 DirectML 디바이스에 직접 적재.

    DirectML은 bf16 미지원 → 호스트에서 fp16/fp32 변환 후 디바이스로 이동.
    DirectML 실사용 VRAM 천장 ~31GB → 7B는 fp16(14GB)으로 적재해야 활성값 여유 확보.
    safe_open을 텐서 단위로 열고 닫아 mmap 워킹셋을 텐서 1개분으로 한정
    (shard 통째 매핑 시 host RAM 소진 → 스왑 프리징 방지).
    """
    import gc
    cfg = AutoConfig.from_pretrained(model_path, trust_remote_code=True)
    with init_empty_weights():
        model = AutoModelForCausalLM.from_config(cfg, torch_dtype=dtype)
    model.tie_weights()  # 묶인 가중치(예: lm_head=embed) 연결

    # 텐서 → shard 매핑 (index 있으면 사용, 없으면 단일 파일)
    idx = os.path.join(model_path, "model.safetensors.index.json")
    if os.path.exists(idx):
        with open(idx, "r", encoding="utf-8") as f:
            wmap = json.load(f)["weight_map"]
        items = [(n, os.path.join(model_path, s)) for n, s in wmap.items()]
    else:
        shard = sorted(glob.glob(os.path.join(model_path, "*.safetensors")))[0]
        with safe_open(shard, framework="pt", device="cpu") as f:
            items = [(n, shard) for n in f.keys()]

    log(f"  {len(items)} tensors 스트리밍 적재 시작 (host RAM 가용 {ram_avail_gb():.1f}GB)")
    loaded, t0 = 0, time.time()
    for name, shard in items:
        if ram_avail_gb() < RAM_GUARD_GB:
            raise MemoryError(
                f"가용 RAM {ram_avail_gb():.2f}GB < {RAM_GUARD_GB}GB 가드. "
                f"다른 앱을 닫고 재시도하세요(스왑 프리징 방지)."
            )
        with safe_open(shard, framework="pt", device="cpu") as f:
            t = f.get_tensor(name).to(dtype)  # host 변환 (텐서 1개분 피크)
        set_module_tensor_to_device(model, name, device, value=t)
        del t
        loaded += 1
        if loaded % 50 == 0:
            gc.collect()
            log(f"  {loaded}/{len(items)} tensors | RAM 가용 {ram_avail_gb():.1f}GB")

    # tied embeddings(예: 1.5B는 lm_head=embed_tokens 공유) 재연결 — 적재 후 다시 tie해야
    # meta로 남은 lm_head.weight가 로드된 embed 텐서로 채워짐(untied 7B/14B엔 무영향).
    model.tie_weights()
    remaining = [n for n, p in model.named_parameters() if p.is_meta]
    if remaining:
        raise RuntimeError(f"적재 안 된 meta 텐서 {len(remaining)}개: {remaining[:5]}")
    log(f"  적재 완료: {loaded} tensors, {time.time()-t0:.1f}s, RAM 가용 {ram_avail_gb():.1f}GB")
    return model


def load_hqq_onthefly(model_path, device, compute_dtype, nbits=4, group_size=64, skip=("lm_head",)):
    """bf16 원본 체크포인트에서 HQQ 4bit로 즉석 양자화(on-the-fly) 로드 — **레이어 단위 스트리밍**.

    bitsandbytes(gfx1151 wave32/wave64 커널 불일치로 GPU wedge 원인, 2026-07-14 확정)를
    전혀 쓰지 않는 경로. HQQ는 커스텀 HIP 커널이 없고 backward가 dequant+평범한 matmul
    (torchao/HQQ 게이트 테스트 통과, scripts/test_nf4_backward_gate.py)이라 안전하다.

    ★ 2026-07-15 발견: transformers 5.13.1의 `HqqConfig` + `from_pretrained(quantization_config=...)`
    자동경로는 깨져 있다 — `transformers/quantizers/base.py:289 get_quantize_ops()`가 최근 리팩터로
    추상 인터페이스가 됐는데 `quantizer_hqq.py`가 아직 구현을 안 해서 즉시
    `NotImplementedError: QuantizationMethod.HQQ is not available yet` 로 실패한다(실측 확인).
    → transformers 통합을 완전히 우회하고, PASS한 게이트 테스트(test_nf4_backward_gate.py)와
    동일하게 `HQQLinear(linear_layer, quant_config, ...)`를 직접 호출해 각 nn.Linear를
    수동으로 치환한다(peft의 dispatch_hqq는 타입만 보고 HQQLinear면 인식하므로 문제 없음).

    ★★ 2026-07-15 저녁 재설계(중요): 이전 버전은 `stream_load_to_device`로 **bf16 전체를
    먼저 device에 통째로 적재한 뒤** Linear를 순회 양자화했다. 14B(bf16 28GB)는 이 장비
    (통합메모리 ~53GB) 안에서 우연히 맞았을 뿐, **32B(bf16 ~65GB)는 이 방식으로는 애초에
    적재 자체가 불가능**하다(양자화 시작 전에 이미 총 RAM을 넘김 — OOM/wedge 확정, 32B HQQ
    본런 착수 직전에 발견해 수정함). 그래서 이 함수는 이제:
      1) 메타(무가중치) 모델을 만들고 양자화 대상 Linear 목록만 먼저 수집한다.
      2) 비양자화 텐서(embedding/norm/lm_head 등 skip)는 기존처럼 텐서 1개씩 device로 스트리밍.
      3) 양자화 대상 Linear는 **레이어 1개(weight+bias)만** bf16으로 device에 올려 즉시
         HQQLinear로 양자화(del_orig=True로 bf16 원본 즉시 해제) → 다음 레이어로.
    peak 메모리 = (이미 양자화된 레이어들의 4bit 합) + (현재 레이어 1개의 bf16) 뿐이라
    모델 전체 크기와 무관하게 안전하다(32B도 이 경로로 적재 가능해짐).

    HQQBackend.PYTORCH는 ROCm에서 유일하게 지원되는 백엔드(ATEN은 CUDA 전용)이므로
    명시적으로 고정한다.
    """
    import gc
    from hqq.core.quantize import HQQLinear, BaseQuantizeConfig, HQQBackend
    HQQLinear.set_backend(HQQBackend.PYTORCH)  # ROCm: ATEN 불가, PYTORCH(순수 dequant+matmul)만 지원

    cfg = AutoConfig.from_pretrained(model_path, trust_remote_code=True)
    with init_empty_weights():
        model = AutoModelForCausalLM.from_config(cfg, torch_dtype=compute_dtype)
    model.tie_weights()

    # 텐서 → shard 매핑 (stream_load_to_device와 동일한 규칙)
    idx = os.path.join(model_path, "model.safetensors.index.json")
    if os.path.exists(idx):
        with open(idx, "r", encoding="utf-8") as f:
            wmap = json.load(f)["weight_map"]
        shard_of = {n: os.path.join(model_path, s) for n, s in wmap.items()}
    else:
        shard = sorted(glob.glob(os.path.join(model_path, "*.safetensors")))[0]
        with safe_open(shard, framework="pt", device="cpu") as f:
            shard_of = {n: shard for n in f.keys()}

    qcfg_template = BaseQuantizeConfig(nbits=nbits, group_size=group_size, axis=1)

    # 1) 양자화 대상 Linear 수집(메타 트리 순회 — 아직 가중치 없음, 구조/shape만 필요).
    targets = []  # (parent_module, attr_name, child_module, dotted_name)
    quant_tensor_names = set()

    def _collect(module, prefix=""):
        for name, child in list(module.named_children()):
            full = f"{prefix}.{name}" if prefix else name
            if isinstance(child, torch.nn.Linear) and not any(s in full for s in skip):
                targets.append((module, name, child, full))
                quant_tensor_names.add(f"{full}.weight")
                if f"{full}.bias" in shard_of:
                    quant_tensor_names.add(f"{full}.bias")
            else:
                _collect(child, full)

    _collect(model)
    log(f"  HQQ 스트리밍 로드: 양자화대상 Linear {len(targets)}개, "
        f"비양자화 텐서 {len(shard_of) - len(quant_tensor_names)}개 (nbits={nbits} group_size={group_size})")

    # 2) 비양자화 텐서(embedding/norm/skip Linear 등)는 기존처럼 텐서 1개씩 device로 스트리밍.
    t0 = time.time()
    loaded = 0
    for name, shard in shard_of.items():
        if name in quant_tensor_names:
            continue
        if ram_avail_gb() < RAM_GUARD_GB:
            raise MemoryError(
                f"가용 RAM {ram_avail_gb():.2f}GB < {RAM_GUARD_GB}GB 가드. "
                f"다른 앱을 닫고 재시도하세요(스왑 프리징 방지)."
            )
        with safe_open(shard, framework="pt", device="cpu") as f:
            t = f.get_tensor(name).to(compute_dtype)
        set_module_tensor_to_device(model, name, device, value=t)
        del t
        loaded += 1
        if loaded % 50 == 0:
            gc.collect()
    log(f"  비양자화 텐서 {loaded}개 적재 완료 ({time.time()-t0:.1f}s, RAM 가용 {ram_avail_gb():.1f}GB)")

    # 3) 양자화 대상 Linear: 레이어 1개(weight[+bias])만 bf16으로 device에 올려 즉시 HQQ 양자화.
    #    → 어느 시점에도 "전체 모델의 bf16 사본"이 존재하지 않는다(32B도 안전).
    n_quant = 0
    for module, attr, child, full in targets:
        if ram_avail_gb() < RAM_GUARD_GB:
            raise MemoryError(
                f"가용 RAM {ram_avail_gb():.2f}GB < {RAM_GUARD_GB}GB 가드(HQQ 양자화 중, {full})."
            )
        with safe_open(shard_of[f"{full}.weight"], framework="pt", device="cpu") as f:
            w = f.get_tensor(f"{full}.weight").to(compute_dtype)
        has_bias = f"{full}.bias" in quant_tensor_names
        shell = torch.nn.Linear(child.in_features, child.out_features, bias=has_bias,
                                 device=device, dtype=compute_dtype)
        shell.weight.data.copy_(w.to(device))
        del w
        if has_bias:
            with safe_open(shard_of[f"{full}.bias"], framework="pt", device="cpu") as f:
                b = f.get_tensor(f"{full}.bias").to(compute_dtype)
            shell.bias.data.copy_(b.to(device))
            del b
        hqq_layer = HQQLinear(shell, quant_config=qcfg_template, compute_dtype=compute_dtype,
                               device=str(device), del_orig=True)
        setattr(module, attr, hqq_layer)
        n_quant += 1
        if n_quant % 20 == 0:
            torch.cuda.empty_cache()
            gc.collect()
            log(f"  {n_quant}/{len(targets)} Linear 양자화 완료 | RAM 가용 {ram_avail_gb():.1f}GB")
    torch.cuda.empty_cache()
    log(f"  HQQ 스트리밍 치환 완료: Linear {n_quant}개 → HQQLinear(4bit), 총 {time.time()-t0:.1f}s")

    model.tie_weights()

    # ★ 2026-07-21 Mixtral 실측: non-persistent 버퍼(rotary_emb.inv_freq/cos_cached/sin_cached
    #   등)는 state_dict에 없어 위 스트리밍 루프가 안 옮긴다 → init_empty_weights가 CPU에 실제
    #   생성한 채 잔존 → forward apply_rotary_pos_emb의 cos[position_ids]에서 device 불일치
    #   크래시("indices ... on the same device ... (cpu)"). dense(123B)에선 안 걸렸음.
    #   모든 버퍼를 device로 확정한다(파라미터는 위에서 양자화/적재로 이미 device).
    dev_t = torch.device(device).type
    moved_buf = 0
    for name, buf in list(model.named_buffers()):
        if buf.is_meta:
            continue
        if buf.device.type != dev_t:
            set_module_tensor_to_device(model, name, device, value=buf.to(device))
            moved_buf += 1
    if moved_buf:
        log(f"  non-persistent 버퍼 {moved_buf}개 device 이동(rotary inv_freq 등)")

    remaining = [n for n, p in model.named_parameters() if p.is_meta]
    if remaining:
        raise RuntimeError(f"적재 안 된 meta 텐서 {len(remaining)}개: {remaining[:5]}")
    remaining_buf = [n for n, b in model.named_buffers() if b.is_meta]
    if remaining_buf:
        log(f"  [경고] meta 버퍼 {len(remaining_buf)}개 잔존(값없음): {remaining_buf[:3]}")

    # transformers 자동경로를 안 탔으므로 model.quantization_method가 안 설정됨.
    # peft.prepare_model_for_kbit_training이 이 플래그로 hqq 분기(grad-ckpt hook,
    # fp32 업캐스트 제외 등)를 타므로 수동으로 세팅해준다.
    model.quantization_method = "hqq"
    model.hqq_quantized = True
    return model


def load_prequantized_4bit(model_path, compute_dtype, attn_impl=None):
    """사전양자화(bnb nf4) 체크포인트 로드 — 32B 4bit용.

    커스텀 stream_load는 텐서를 fp16/bf16으로 변환해 채우므로 nf4(uint8 packed +
    quant_state)를 못 읽는다. 대신 from_pretrained가 config.json의 quantization_config를
    자동 인식해 Linear4bit 모듈을 만들고 quant_state까지 적재한다(bnb-ROCm 필요).
    device_map={'':0}으로 단일 GPU에 직접 올린다.
    """
    log(f"  사전양자화(4bit) 로드: from_pretrained device_map=cuda:0, compute_dtype={compute_dtype}"
        + (f", attn_implementation={attn_impl}" if attn_impl else ""))
    kw = {}
    if attn_impl:
        # gfx1151 backward 웨지 회피: 실험적 mem-efficient SDPA 대신 eager(math) 어텐션.
        kw["attn_implementation"] = attn_impl
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        device_map={"": 0},
        dtype=compute_dtype,
        trust_remote_code=True,
        **kw,
    )
    return model


def build(model_path, device, config, dtype, grad_ckpt, load_4bit=False, attn_impl=None,
          quant="none", hqq_nbits=4, hqq_group_size=64):
    log(f"모델 로드: {model_path} (dtype={dtype}"
        + (', 4bit-prequant(bnb)' if load_4bit else '')
        + (f', hqq-{hqq_nbits}bit-onthefly' if quant == "hqq" else '') + ")")
    tok = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    kbit = load_4bit or (quant == "hqq")
    if quant == "hqq":
        model = load_hqq_onthefly(model_path, device, dtype,
                                   nbits=hqq_nbits, group_size=hqq_group_size)
    elif load_4bit:
        model = load_prequantized_4bit(model_path, dtype, attn_impl=attn_impl)
    else:
        model = stream_load_to_device(model_path, device, dtype)

    if kbit:
        from peft import prepare_model_for_kbit_training
        model = prepare_model_for_kbit_training(
            model, use_gradient_checkpointing=grad_ckpt)

    lc = config["lora"]
    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=lc["r"], lora_alpha=lc["lora_alpha"],
        target_modules=lc["target_modules"],
        lora_dropout=lc["lora_dropout"], bias=lc["bias"],
    )
    model = get_peft_model(model, lora_config)
    if not kbit:
        model = model.to(device)  # LoRA 신규 파라미터를 디바이스로 (4bit/hqq는 이미 device_map으로 GPU에 있고 .to() 불가)
    model.config.use_cache = False

    # gradient checkpointing: DirectML에서는 재계산이 캐싱 할당자에 버퍼를 더 쌓아
    # 오히려 VRAM 증가를 가속 → 기본 비활성.
    # kbit(4bit/hqq) 경로는 prepare_model_for_kbit_training이 이미 grad-ckpt를 처리하므로 재적용 안 함.
    if grad_ckpt and not kbit:
        model.gradient_checkpointing_enable()
        model.enable_input_require_grads()

    model.print_trainable_parameters()
    return model, tok


def make_loader(data_file, tok, max_len, batch_size, shuffle, add_eos=True):
    ds = load_dataset("json", data_files=data_file, split="train")

    def tok_fn(ex):
        # ★ EOS 위생(2026-06-18): 각 텍스트 끝에 eos(<|im_end|>) 부착. pad=<|endoftext|>로
        #   eos와 달라 라벨에 살아남음 → 모델이 정지를 학습(### 누수·런온 방지).
        #   단 R3에서 회귀 관측 → --no-eos로 끄면 seq512(pre-EOS) 레시피 재현.
        texts = [(t + tok.eos_token) if add_eos else t for t in ex["text"]]
        # 고정 길이 패딩: 모든 배치를 동일 크기로 → DirectML 할당자 버퍼 재사용
        # (동적 패딩 시 배치마다 크기가 달라 VRAM이 step마다 증가 → OOM)
        return tok(texts, truncation=True, max_length=max_len,
                   padding="max_length")

    ds = ds.map(tok_fn, batched=True, remove_columns=ds.column_names)
    collator = DataCollatorForLanguageModeling(tokenizer=tok, mlm=False)
    return DataLoader(ds, batch_size=batch_size, shuffle=shuffle, collate_fn=collator)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", type=int, default=0,
                    help="스모크 모드: 지정 step 수만 돌리고 저장 없이 종료")
    ap.add_argument("--config", default="./config/training_config.yaml")
    ap.add_argument("--backend", choices=["auto", "directml", "cuda"], default="directml",
                    help="연산 백엔드. directml=Windows기본. cuda=ROCm/HIP(empty_cache·bf16·env var 작동→고seq). auto=cuda있으면 cuda")
    ap.add_argument("--dtype", choices=["fp16", "fp32", "bf16"], default="fp16",
                    help="가중치 dtype. fp16=DirectML기본. bf16=ROCm/CUDA만(스케일 불필요·수치안정)")
    ap.add_argument("--empty-cache-every", type=int, default=-1,
                    help="N optim step마다 empty_cache(단편화 해소). -1=auto(cuda:1,directml:0), 0=끔. directml은 무효")
    ap.add_argument("--seq", type=int, default=0, help="max_seq_length 오버라이드(0=config)")
    ap.add_argument("--scale", type=float, default=128.0,
                    help="fp16 손실 스케일(언더플로 방지)")
    ap.add_argument("--grad-ckpt", action="store_true",
                    help="gradient checkpointing(DirectML에서는 비권장)")
    ap.add_argument("--out", default="", help="출력 디렉터리 오버라이드(0=config)")
    ap.add_argument("--lora-r", type=int, default=0, help="LoRA r 오버라이드(0=config). α는 2r로 동반 조정")
    ap.add_argument("--lora-mlp", action="store_true",
                    help="MLP(gate/up/down_proj)도 LoRA 타깃에 추가(capacity 확대)")
    ap.add_argument("--train-file", default="", help="train_file 오버라이드(빈값=config)")
    ap.add_argument("--base", default="", help="base_model 오버라이드(빈값=config). 14B 등 다른 베이스용")
    ap.add_argument("--epochs", type=int, default=0, help="num_train_epochs 오버라이드(0=config)")
    ap.add_argument("--optim", choices=["adamw", "sgd"], default="adamw",
                    help="옵티마이저. sgd=상태 적음→메모리 절감+lerp CPU폴백 회피(14B 고seq용)")
    ap.add_argument("--momentum", type=float, default=0.9, help="SGD 모멘텀(0=상태 0, 최대 절감)")
    ap.add_argument("--no-eos", action="store_true",
                    help="EOS 위생 끔(seq512 pre-EOS 레시피 재현 — R3 회귀 회피)")
    ap.add_argument("--load-4bit", action="store_true",
                    help="사전양자화(bnb nf4) 체크포인트 로드(32B용). from_pretrained가 config의 "
                         "quantization_config 자동인식→Linear4bit. bnb-ROCm 필요. dtype=bf16(compute)")
    ap.add_argument("--attn-eager", action="store_true",
                    help="gfx1151 backward 웨지 회피(2026-07-14 발견): 실험적 mem-efficient SDPA 대신 "
                         "eager(math) 어텐션 사용 + SDP flash/mem-efficient 백엔드 비활성. 4bit smoke 실패 시 #1 시도.")
    ap.add_argument("--quant", choices=["none", "hqq"], default="none",
                    help="none=기존(bf16 stream 또는 --load-4bit bnb). "
                         "hqq=bitsandbytes 미사용, bf16 원본에서 HQQ 4bit 즉석 양자화(2026-07-15, gate 통과 경로). "
                         "bf16 원본이 디스크에 있는 모델에만 적용 가능(32B는 bnb-prequant뿐이라 불가).")
    ap.add_argument("--hqq-nbits", type=int, default=4, help="HQQ 비트수(기본 4)")
    ap.add_argument("--hqq-group-size", type=int, default=64, help="HQQ group_size(기본 64)")
    args = ap.parse_args()

    if args.quant == "hqq" and args.load_4bit:
        raise SystemExit("--quant hqq와 --load-4bit(bnb)는 동시 사용 불가(서로 다른 4bit 포맷).")

    if args.attn_eager:
        # 실험적 AMD SDPA 커널을 backward에서 배제(gfx1151 launch-failure 회피).
        try:
            torch.backends.cuda.enable_flash_sdp(False)
            torch.backends.cuda.enable_mem_efficient_sdp(False)
            torch.backends.cuda.enable_math_sdp(True)
        except Exception as _e:
            pass

    config = load_config(args.config)
    # LoRA capacity 오버라이드(품질 튜닝용)
    if args.lora_r > 0:
        config["lora"]["r"] = args.lora_r
        config["lora"]["lora_alpha"] = args.lora_r * 2
    if args.lora_mlp:
        tm = list(config["lora"]["target_modules"])
        for m in ["gate_proj", "up_proj", "down_proj"]:
            if m not in tm:
                tm.append(m)
        config["lora"]["target_modules"] = tm
    backend, device, dev_name, empty_cache, mem_used_gb = resolve_backend(args.backend)

    # dtype 해석 + 백엔드 호환 가드
    req_dtype = args.dtype
    if backend == "directml" and req_dtype == "bf16":
        log("⚠ DirectML은 bf16 미지원 → fp16으로 강제")
        req_dtype = "fp16"
    dtype = {"fp16": torch.float16, "bf16": torch.bfloat16, "fp32": torch.float32}[req_dtype]
    use_scale = dtype == torch.float16  # bf16/fp32는 손실 스케일 불필요
    SCALE = args.scale if use_scale else 1.0

    # empty_cache 주기: -1=auto(cuda:매 step, directml:끔)
    ec_every = args.empty_cache_every
    if ec_every < 0:
        ec_every = 1 if backend == "cuda" else 0

    log(f"디바이스: {backend} ({dev_name}) | dtype={req_dtype} "
        f"| loss_scale={SCALE if use_scale else 'off'} | empty_cache_every={ec_every}")
    log(f"시작 RAM 가용 {ram_avail_gb():.1f}GB / CPU {psutil.cpu_percent()}%")

    tcfg = config["training"]
    dcfg = config["data"]
    model_path = args.base if args.base else config["model"]["base_model"]

    model, tok = build(model_path, device, config, dtype, args.grad_ckpt,
                       load_4bit=args.load_4bit,
                       attn_impl=("eager" if args.attn_eager else None),
                       quant=args.quant, hqq_nbits=args.hqq_nbits,
                       hqq_group_size=args.hqq_group_size)

    bs = tcfg["per_device_train_batch_size"]
    accum = tcfg["gradient_accumulation_steps"]
    max_len = args.seq if args.seq > 0 else dcfg["max_seq_length"]

    train_file = args.train_file if args.train_file else dcfg["train_file"]
    add_eos = not args.no_eos
    log(f"train_file={train_file} | EOS위생={'on' if add_eos else 'off(pre-EOS)'}")
    train_loader = make_loader(train_file, tok, max_len, bs, shuffle=True, add_eos=add_eos)
    smoke = args.smoke > 0
    val_loader = (None if smoke
                  else make_loader(dcfg["val_file"], tok, max_len, bs, shuffle=False, add_eos=add_eos))

    trainable = [p for p in model.parameters() if p.requires_grad]
    _lr = float(tcfg["learning_rate"])
    if args.optim == "sgd":
        optim = torch.optim.SGD(trainable, lr=_lr, momentum=args.momentum)
        log(f"옵티마이저=SGD(momentum={args.momentum}) — 메모리 절감/lerp폴백 회피")
    else:
        optim = torch.optim.AdamW(trainable, lr=_lr, eps=1e-4)

    smoke = args.smoke > 0
    epochs = 1 if smoke else (args.epochs if args.epochs > 0 else int(tcfg["num_train_epochs"]))
    total_steps = (len(train_loader) // accum) * epochs
    sched = get_cosine_schedule_with_warmup(
        optim, int(total_steps * tcfg["warmup_ratio"]), max(total_steps, 1)
    )

    log(f"{'[스모크]' if smoke else '[본런]'} epochs={epochs} "
        f"batches/epoch={len(train_loader)} accum={accum} "
        f"optim_steps≈{total_steps if not smoke else args.smoke}")

    @torch.no_grad()
    def eval_loss():
        if val_loader is None:
            return None
        model.eval()
        tot, n = 0.0, 0
        for b in val_loader:
            b = {k: v.to(device) for k, v in b.items()}
            tot += model(**b).loss.item()
            n += 1
        model.train()
        return tot / max(n, 1)

    # ── 무인 장시간 학습 안전장치: 주기 체크포인트 + SIGTERM/SIGINT 저장 (non-smoke 전용) ──
    # 두목 5시 수동중단(systemd stop→SIGTERM)/크래시 대비 진척 보존. smoke는 저장 안 함(미접촉).
    out_dir = args.out if args.out else tcfg["output_dir"]
    SAVE_EVERY = 25  # optim_step 단위 주기 저장
    _stop_req = {"v": False}
    def _on_term(signum, frame):
        _stop_req["v"] = True
        log(f"[신호 {signum}] 중단 요청 접수 — 다음 step 경계에서 저장 후 종료")
    if not smoke:
        signal.signal(signal.SIGTERM, _on_term)
        signal.signal(signal.SIGINT, _on_term)
    def _save_adapter(tag=""):
        try:
            os.makedirs(out_dir, exist_ok=True)
            from peft import get_peft_model_state_dict
            import safetensors.torch as _st
            sd_cpu = {k: v.detach().to("cpu").float()
                      for k, v in get_peft_model_state_dict(model).items()}
            an = list(model.peft_config.keys())[0]
            model.peft_config[an].save_pretrained(out_dir)
            _st.save_file(sd_cpu, os.path.join(out_dir, "adapter_model.safetensors"))
            tok.save_pretrained(out_dir)
            log(f"[체크포인트{tag}] 저장 {out_dir} (step {step}, 어댑터 {len(sd_cpu)} 텐서, CPU/fp32)")
            return True
        except Exception as e:
            log(f"[체크포인트 저장 실패{tag}] {type(e).__name__}: {e}")
            return False

    model.train()
    run_start = time.time()
    step, micro = 0, 0
    step_times = []
    win_loss = 0.0  # accum 윈도우 손실 합(평균 로깅용)
    t_step = time.time()
    stop = False

    skipped = 0
    for ep in range(epochs):
        for batch in train_loader:
            batch = {k: v.to(device) for k, v in batch.items()}
            out = model(**batch)
            win_loss += out.loss.item()
            (out.loss * SCALE / accum).backward()
            micro += 1

            if micro % accum == 0:
                # fp16 그래디언트 언스케일 + inf/nan 검사
                bad = False
                for p in trainable:
                    if p.grad is not None:
                        if SCALE != 1.0:
                            p.grad.div_(SCALE)
                        if not torch.isfinite(p.grad).all():
                            bad = True
                if bad:
                    skipped += 1  # 스케일 오버플로 → 이 step 건너뜀
                else:
                    optim.step()
                optim.zero_grad()
                sched.step()
                step += 1
                # 단편화 해소: cuda(ROCm)에서 캐시 블록 반환 → 고seq 안정(directml은 no-op).
                if ec_every and step % ec_every == 0:
                    empty_cache()
                dt_step = time.time() - t_step
                step_times.append(dt_step)
                # 윈도우 평균 손실(=실질 step 손실). 단일 마이크로배치가 아니라 accum 평균.
                avg_loss = win_loss / accum
                win_loss = 0.0
                gpu_str = f" | GPU {mem_used_gb():.1f}GB" if backend == "cuda" else ""
                log(f"step {step} | loss(avg{accum}) {avg_loss:.4f} | "
                    f"{dt_step:.1f}s/step | RAM가용 {ram_avail_gb():.1f}GB{gpu_str} | "
                    f"CPU {psutil.cpu_percent()}%{' | SKIP(nan)' if bad else ''}")
                t_step = time.time()
                if not smoke:
                    if _stop_req["v"]:
                        _save_adapter("-signal"); stop = True; break
                    if step % SAVE_EVERY == 0:
                        _save_adapter(f"-step{step}")
                if smoke and step >= args.smoke:
                    stop = True
                    break
        if stop:
            break
        vl = eval_loss()
        if vl is not None:
            log(f"  [epoch {ep+1}/{epochs}] val_loss {vl:.4f}")
    if skipped:
        log(f"  (참고: nan/inf로 건너뛴 step {skipped}개)")

    elapsed = time.time() - run_start
    avg = sum(step_times) / len(step_times) if step_times else 0
    log(f"종료: {step} steps, 총 {elapsed:.1f}s, 평균 {avg:.1f}s/step")

    if smoke:
        log("[스모크 완료] 저장 생략. backward 정상 동작 확인됨." if step > 0
            else "[스모크 실패] step 미완료.")
        return

    # 저장: 어댑터 가중치를 CPU/fp32로 옮겨 직접 저장(위 _save_adapter 재사용).
    # (DirectML 텐서는 safetensors가 storage 조회 불가라 PEFT save_pretrained 실패 → 직접 저장)
    _save_adapter("-final")
    log(f"[본런 완료] 최종 저장 완료: {out_dir}")


if __name__ == "__main__":
    main()
