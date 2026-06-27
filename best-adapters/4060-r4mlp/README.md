# 4060 베스트 어댑터 — r4mlp (held-out 95%)

4060 노드(RTX 4060 8GB, CUDA)의 최고 React JS→TS 어댑터. 공동보관(8060↔4060 핸드오프·재현용).

## 식별
- **base**: `Qwen/Qwen2.5-Coder-7B`(코드특화 7B). 4bit nf4 QLoRA로 학습, 측정도 4bit.
- **LoRA**: r16, alpha32, **target=qkvo_mlp**(q,k,v,o,gate,up,down 7모듈, trainable 40M). dropout 0.05.
- **seq** 768, **epochs** 3, adamw_8bit. 데이터=합성 296쌍(라운드4 import보존+제네릭 19쌍 포함; eval/held-out 파일 미투입).
- adapter_model.safetensors 154MB(LFS), adapter_config.json.

## 성적 (최종 하니스: per-file 단독컴파일, LF, TS2347제외, max_new=2048)
- **held-out(4060 미학습 egov 4파일) = 95.0%** (3/4 clean). ← 진짜 일반화. rank16은 55%로 붕괴.
- 11태스크 = 90.9%. (8060 seq512 81.8%, 8060 R3 65.5% 대비 우세)
- ★용량 레버(+MLP)가 유일 성공. 데이터양↑(r5)·에폭↑(r4mlpq)·다른베이스(Qwen3-8B)는 전부 회귀.

## 사용
```bash
# base는 HF서 재다운로드: Qwen/Qwen2.5-Coder-7B
python scripts/eval_hard_tsc.py --adapter best-adapters/4060-r4mlp --heldout --max-new 4096
# 또는 PeftModel.from_pretrained(base_4bit, "best-adapters/4060-r4mlp")
```
규약: `comms/README.md`. 약점·증류 계획: `comms/error-taxonomy.md`.
