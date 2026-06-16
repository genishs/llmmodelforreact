# 7B QLoRA 학습 벤치마크 (CUDA / NVIDIA RTX 4060 Laptop 8GB)

날짜: 2026-06-16 · 장비: Intel UHD + **NVIDIA RTX 4060 Laptop GPU 8GB** (CUDA)

> 이 문서는 **NVIDIA 4060(CUDA) 버전**이다. AMD Radeon 8060S(DirectML)에서 같은 7B를
> 학습한 기록은 [training-benchmark-7b.md](training-benchmark-7b.md)를 참고. 그 DirectML
> 작업은 통합메모리 48GB 카브아웃으로 7B fp16을 GPU에 올려 6분에 학습을 끝낸 의미 있는
> 성과였고, 동시에 **seq 256/384 한계로 데이터의 51%가 잘리는** 품질 제약을 실측으로
> 드러냈다. 이 CUDA 버전은 4비트 양자화로 그 제약(잘림)을 푸는 것이 목표다.

## 결론 요약

| 항목 | 값 |
|------|----|
| 모델 | Qwen2.5-Coder-**7B**, 4비트 QLoRA(nf4 + double quant) |
| LoRA | r=16 / α=32 (q,k,v,o_proj), **학습 파라미터 10,092,544 (0.13%)** |
| 정밀도 | 4비트 가중치 + fp16 compute (Ada는 bf16도 가능) |
| 데이터 | train 272 / val 31 = 303개, **max_seq 768 (잘림 0건)** |
| 스케줄 | 3 epoch × 34 = **102 optim step** (accum 8) |
| **학습 시간** | **1182초 (19.7분), 안정 시 ~11초/step** |
| **train_loss / eval_loss** | **0.5497 / 0.4709** (epoch별 0.498→0.471→0.471) |
| VRAM | ~7.6GB (8GB 한계 바로 아래에서 안정) |
| 결과물 | `models/qwen-react-lora-7b-qlora/adapter_model.safetensors` (40.4MB) |
| 추론 속도 | 7B 4비트 **~14 tok/s** (DirectML fp16의 ~9 tok/s 대비 빠름) |

> DirectML(seq 384, 169개)과 직접 비교는 아래 "AMD vs CUDA"를. **데이터 잘림이 사라진 것이
> 핵심 차이**이며, 실제 출력 품질에서 큰 격차로 나타난다.

## 8GB GPU에서 7B QLoRA를 실제로 굴리며 밝혀낸 것 (중요)

`setup-other-pc.md`는 "4060에서 seq 1024 QLoRA가 된다"고 적었으나 **미검증**이었다. 실제로
돌려보니 기본 `train_qlora.py`는 **step이 10초 → 60 → 170초로 급락**하며 사실상 못 끝낸다.
원인을 실측으로 추적해 고쳤다:

1. **`prepare_model_for_kbit_training`의 fp32 업캐스트가 주범.**
   이 함수는 4비트가 아닌 파라미터를 fp32로 올린다. 7B의 `embed_tokens`·`lm_head`(각
   152k×3584)가 **bf16 1.09GB → fp32 2.18GB**가 되어 둘이 +2.2GB. 로드 직후 5.56GB가
   **prepare 직후 7.74GB**로 뛴다(실측). 4비트 베이스와 합쳐 8GB를 넘기면 NVIDIA Windows
   드라이버가 **공유 시스템 메모리(WDDM)로 스필** → GPU util 100%인데 전력 28W(=연산이
   아니라 PCIe 전송 대기). 이 둘은 LoRA 대상이 아니어서 학습되지 않으므로 **fp16으로 되돌려
   2.2GB를 회수**한다.
2. **캐싱 할당자의 reserved 메모리가 step마다 누적(단편화)** → 처음 ~16step은 9초였다가
   다시 8GB를 넘겨 스필. **매 optim step 후 `gc.collect()`+`torch.cuda.empty_cache()`**
   콜백으로 ceiling 아래 유지(`expandable_segments:True`만으론 부족했다).
3. **`paged_adamw_8bit` → `adamw_8bit`.** LoRA는 학습 파라미터가 10M로 옵티마이저 상태가
   수십 MB뿐 → CPU 페이징(통합메모리)이 불필요하고 Windows에서 느림. in-VRAM 8bit로 충분.
4. **`per_device_eval_batch_size=1`.** 기본 8이면 step 50 eval에서 VRAM이 급증해 스필.
5. **seq는 768로 충분.** 학습셋 실측 토큰 길이 **최대 713 / 평균 263 / p95 469**,
   768 초과 0건. seq 1024는 과대 설정(메모리만 낭비). 768로도 **잘림 0건**.

> 위 4가지 수정은 `src/train_qlora.py`에 반영됨. 수정 후 step이 ~11초로 안정되어 102 step을
> 19.7분에 완주. **8GB에서 7B QLoRA는 "되긴 되지만, 위 메모리 처치 없이는 못 한다"** 가 결론.

## 재현 방법

```bash
venv\Scripts\activate
# 1) 데이터 빌드(seq 768에 맞춰 — 실제로는 cap 1024로 빌드해도 모두 768 이하라 동일)
python src/build_dataset_v2.py --cap 1024 --gh-out-cap 512   # → 303개(272/31)
# 2) QLoRA 학습 (메모리 처치 포함된 train_qlora.py)
set PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
python src/train_qlora.py --seq 768 --out ./models/qwen-react-lora-7b-qlora
```

## AMD vs CUDA — 같은 조건 비교 (핵심)

두 어댑터를 **같은 4060 · 같은 7B 4비트 베이스 · greedy 디코딩 · 같은 프롬프트**로 돌렸다
(`scripts/compare_adapters.py`). 하드웨어/베이스/디코딩이 동일하므로 차이는 **학습된 어댑터**
에서만 온다.

| 비교 대상 | 학습 환경 | 데이터 | seq | eval_loss |
|-----------|-----------|--------|-----|-----------|
| **AMD-DirectML-v4** | Radeon 8060S, fp16 커스텀 루프 | 169 | 384 (51% 잘림) | 4.06\* |
| **CUDA-QLoRA** | RTX 4060, 4비트 HF Trainer | 303 | 768 (잘림 0) | 0.4709\* |

> \* loss 값은 **스케일이 달라 직접 비교 불가**(DirectML 커스텀 루프 vs HF Trainer의 손실
> 계산·마스킹 차이). 품질 판단은 아래 실제 출력으로 한다.

추론 속도·메모리는 동일: 둘 다 **~14 tok/s, VRAM peak 5.89GB**. **차이는 오직 출력 품질**:

| 프롬프트 | AMD-DirectML-v4 | CUDA-QLoRA |
|----------|-----------------|------------|
| 카운터(EN) | 동작하나 **정지 실패** — 무관한 ToDo까지 계속 생성(320tok) | 깔끔히 완성 후 정지(113tok) |
| useWindowSize(KR) | 양호(설명 장황) | 양호(간결) |
| **useDebounce\<T\>(TS 제네릭)** | **깨짐**: `'type' is not assignable to type 'never'`(19tok) | **완벽**: 제네릭+setTimeout 클린업(95tok) |
| **TanStack 무한스크롤(KR 복잡)** | **실패**: 지시문만 되풀이, 코드 0줄(42tok) | **성공**: useInfiniteQuery+Product 타입+로딩/에러 처리 |

**해석:** AMD-v4가 깨지는 항목(TS 제네릭, 복잡/긴 출력)은 정확히 **seq 384 잘림 + 데이터 부족**
의 후유증이다. CUDA(seq 768, 잘림 0, 데이터 303)에서 그 항목들이 모두 해결됐다.

## egovGeoportal 실파일 테스트

테스트 프로젝트: `d:\Documents\workspace\TwinSpace\egovGeoportal`
(React 18 + Vite + Redux Toolkit, **.jsx 84개 / .tsx 0개** — 전부 JS, TypeScript 0).
→ 이 프로젝트의 실제 니즈인 **JS→TS 변환**으로 테스트(`scripts/test_on_file.py`).

대상 파일: `src/components/EgovPaging.jsx` (페이징 컴포넌트, **입력 840 토큰**)
지시: "이 React 컴포넌트를 TypeScript로 변환해줘. props 타입을 interface로 정의해줘."

| 어댑터 | 결과 |
|--------|------|
| **AMD-DirectML-v4** | **빈 출력(0자)** — 840토큰 입력이 seq384 학습 분포 밖이라 붕괴 |
| **CUDA-QLoRA** | **성공** — `interface Props` 정의, `??` 적용, 페이지 루프를 `Array.from`으로 리팩터링, console.log 제거. 바로 쓸 만한 `.tsx` |

CUDA 출력(발췌):
```tsx
interface Props {
  pagination?: { currentPageNo: number; totalRecordCount: number; recordCountPerPage: number; pageSize: number };
  moveToPage: (pageNo: number) => void;
}
function EgovPaging({ pagination, moveToPage }: Props) {
  const currentPageNo = pagination?.currentPageNo ?? 1;
  ...
}
```
> 미세 결함: `tabIndex="0"`는 TS에서 `tabIndex={0}`이 맞고, `style={{opacity}}`/내부 `num_on1`
> div는 단순화 과정에서 누락. 그래도 실파일 변환을 **완주**한 점이 AMD-v4(0자)와 결정적 차이.

**결론:** 실제 프로젝트 파일처럼 입력이 길어질수록 seq384 학습 모델은 무너지고, CUDA seq768
모델만 동작한다. egovGeoportal의 84개 .jsx → .tsx 변환에는 **CUDA-QLoRA 어댑터를 쓸 것.**

## 서빙 전환

```bash
# model_loader.py의 7b ADAPTER_PATH를 qwen-react-lora-7b-qlora로 바꾸거나,
set REACT_ASSISTANT_MODEL=7b
python src/serve_api.py
```
(현재 `model_loader.py`의 7b 기본 경로는 `qwen-react-lora-7b-v4`. CUDA 학습본을 서빙하려면
해당 경로를 `qwen-react-lora-7b-qlora`로 변경.)

## 품질 기대치 / 다음 단계

- 1.5B(fp16) 추론도 CUDA에서 검증됨 — 가볍고 빠름(작은 컴포넌트·표준 훅).
- 7B(4비트) CUDA-QLoRA — TS 제네릭·복잡 컴포넌트·**실파일 변환**까지 일관성 있음.
- 더 키우려면: ① 다른 분포 데이터(멀티파일 컨텍스트, 복잡 실무 컴포넌트)
  ② egovGeoportal에서 좋은 .tsx 변환 결과를 데이터로 환류 ③ eval_loss는 이미 epoch2에서
  포화(0.471) → epoch/LR보다 데이터 다양성이 다음 레버.
