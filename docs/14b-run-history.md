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

### S5. 어댑터 벤치 비교 — 캐논 held-out 측정 ✅ (2026-06-28)
실행: `eval_hard_tsc_dml.py --adapter qwen-react-lora-14b-v1 --label 8060-14b-v1-seq256e2 --heldout --max-new 4096 --base <14B snapshot>`
(이 단계 위해 `eval_hard_tsc_dml.py`에 `--base` 오버라이드 추가.)
- **결과: SCORE 4.40/7 = 62.9%** (clean 3/7, errs 14). `eval_results/8060-14b-v1-seq256e2.json`, `scores-8060.jsonl` 등록.
- per_task: select 1.0 · gallery 0.8(TS2554) · about-org 1.0 · **attachfile 0.0**(TS18047 null·2322·2345·2554) · admin-dae 1.0 · admin-mlist 0.6(TS2554×2) · **admin-medit(22KB) 0.0**(4096잘림→TS17008).
- **정직한 해석**: 공통4태스크 비교 시 14B=70% < 8060 r5mlp 80% < 4060 r4mlp 95%. "큰 베이스"만으론 부족 — 이번 14B는 qkvo만(MLP無)+r4데이터+seq256 구성이라 4060이 증명한 레버(qkvo_mlp+데이터)를 미적용. ∴ 용량레버·데이터 > base크기.
- **운영 교훈**: 22KB 입력+4096생성 시 호스트 RAM 2.1GB까지 압박(SIGKILL 직전)·태스크당 ~20분. 마지막 medit 태스크가 병목. 워처는 PID 단위 사망감지로(잔류 python 오탐 회피). 살림툴 `scripts/score_saved_dml.py`(저장본 오프라인 채점) 준비.
- ⚠️ 측정기준 변경: 이번이 **새 캐논 heldout7-mn4096 첫 측정**(기존은 heldout4-mn2048) → 직접비교는 공통태스크로만. 4060에 r4mlp 새 캐논 재측정 요청함.

### S5b. (다음 후보) 14B qkvo_mlp 또는 seq512
이번 결과로 방향: ① **14B를 qkvo_mlp(+MLP 레버)로 재학습** — 4060이 증명한 일반화 레버를 14B에 적용(가장 유망), 또는 ② seq512 본진(고정seq 메모리안정). 둘 다 재부팅 클린 후 GPU 여유 확보 권장.

### S6. (예정) seq512 본진
재부팅 클린 후 seq512(7B 챔피언과 동조건) 본진 학습 → 동일 캐논 측정 → scores 등록.
