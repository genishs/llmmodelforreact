# 14B fp16 LoRA — 단계별 실행 이력 (8060)

> 8060(AMD 8060S / DirectML / Windows)에서 Qwen2.5-Coder-14B fp16 LoRA를 학습·측정한 전 과정 타임라인.
> 4060과의 캐치볼 정본은 `comms/from-8060.md` + `comms/scores-8060.jsonl`. 이 문서는 8060측 내러티브 인덱스.
> **append 위주, 시간 오름차순.** 새 단계는 맨 아래에 추가한다.

## 환경 고정값
- 베이스: `~/.cache/huggingface/hub/models--Qwen--Qwen2.5-Coder-14B-Instruct/snapshots/aedcc2d4…` (fp16, 579 tensors, 29GB)
- 디바이스: DirectML / AMD Radeon 8060S / fp16 / loss_scale=128
- LoRA: r16, qkvo, dropout0.05, bias none (trainable 25.2M / 0.17%)
- 데이터: `data/processed/react_train_r4.jsonl` (299 샘플), val 별도, EOS위생 on
- 측정 캐논(양 노드 합의): `eval_hard_tsc_dml.py --heldout --max-new 4096`, per-file 단독컴파일, LF정규화,
  score=1.0 if errs==0 else max(0,1-errs/5), TS2347 제외, greedy+min_new24+reppen1.1

## 타임라인

### S1. 14B 적재·1스텝 실증 (2026-06-27, ~Stage1~3)
29GB fp16를 DirectML GPU에 스트리밍 적재 성공(37s). 관문=호스트 RAM(시작 ~6GB+ 여유 필수,
~3GB면 큰 텐서 복사 중 OS SIGKILL). LoRA forward(loss 11.26)→backward→AdamW 1스텝 완주.
GPU 피크 ~30~32GB(39 천장 아래). **결론: 14B fp16 LoRA가 DirectML/Windows에서 학습 가능(실증).**

### S2. seq 안정상한 탐색 (2026-06-27)
`probe_14b_seqsweep.py`(29GB 1회적재 후 오름차순 1스텝): seq128✅ 256✅ 384✅ **512✅** 768❌(DML OOM).
→ 클린프로세스 실학습 안정상한 **seq512** 확정. (반복 probe로 GPU 잔여 누적 시 384도 OOM — DirectML `empty_cache` 부재.)

### S3. 실데이터 학습 1차 (seq256, 1epoch) — 2026-06-27 ~22:00
잔여 누적 상태라 안전하게 seq256 안착. r4 299샘플 1epoch, 37 optim스텝 완주.
**val_loss 2.37**, 24.9s/step, OOM 0. 어댑터 저장 `models/qwen-react-lora-14b-v1`(384텐서 100MB, 로컬보관).

### S4. 본런 — seq256, 2epoch (`train14b_v1_256e2`) — 2026-06-27 22:36~
재개 세션. epochs=2, batches/epoch=299, accum=8, **총 optim_steps≈74**.
- **epoch 1/2 val_loss 2.1329** (S3의 1epoch 2.37 대비 개선) — 22:53
- epoch 2 진행 중 (이력 기록 시점 step ~66/74, ~25s/step, OOM 0)
- ⚠️ 학습 도중 감시(Monitor) 스크립트가 exit 254로 죽어 *세션*이 끊겼으나 **학습 프로세스는 무관하게 계속됨**.
  새 세션에서 재점검·감시 재무장 후 완주 대기 중.
- 어댑터는 epoch 2 완주 후 1회 저장(`train_directml.py:331`). → 중단 금지, 완주 필수.

### S5. (예정) 어댑터 벤치 비교 — 캐논 held-out 측정
완주 직후 자동 실행:
```
python scripts/eval_hard_tsc_dml.py \
  --adapter models/qwen-react-lora-14b-v1 \
  --label 8060-14b-v1-seq256e2 --heldout --max-new 4096 \
  --base "<14B snapshot 경로>"
```
→ `eval_results/8060-14b-v1-seq256e2.json` 생성 → 점수 `scores-8060.jsonl` append → 4060 7B r4mlp와 대조.
(이번 단계 위해 `eval_hard_tsc_dml.py`에 `--base` 오버라이드 추가함.)

### S6. (예정) seq512 본진
재부팅 클린 후 seq512(7B 챔피언과 동조건) 본진 학습 → 동일 캐논 측정 → scores 등록.
