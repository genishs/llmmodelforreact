# CLAUDE.md — ai_model 프로젝트 운영 룰 (정본)

> 이 파일이 이 프로젝트의 **작업 규칙 정본**이다. (개인 세션 메모리가 아니라 레포에 커밋되어
> 모든 세션·기여자가 공유한다.) 상충 시 이 파일을 우선한다.

## 프로젝트
AMD Ryzen AI Max+ 392(Strix Halo, Radeon 8060S/DirectML) **로컬 디바이스에서 직접 LoRA
학습·구동**하는 React 특화 코딩 어시스턴트. 베이스 Qwen2.5-Coder, peft + torch-directml +
FastAPI + MCP. GitHub: `genishs/llmmodelforreact`(main).

## 하드웨어·메모리 제약 (실측 — 추측 금지, 이 수치로 판단)
- **GPU 카브 = 전용 48GB / 호스트 RAM 15.6GB** (64GB 통합메모리, BIOS VGM 48GB).
- **GPU 텐서 실사용 천장 ≈ 39GB** (`scripts/dml_ceiling_probe.py` 실측: fp16 0.5GB씩 적재 →
  ~39GB 도달 후 **세그폴트**, 깔끔 OOM 아님). **과거 "28GB 천장"은 틀림** — 28GB는
  GPU 예산 캡이 아니라 **학습 단편화 벽**이었다.
- **균일-probe 39GB vs 실학습 28~31GB = 단편화 격차 ~8~11GB**. 원인: DirectML 캐싱 할당자가
  step마다 증가하는데 **`empty_cache` API가 없음** (`torch_directml`엔 `gpu_memory`=30카운터
  리스트뿐, 측정도 불안정). 단편화 억제(고정 seq 패딩·일관 배치)가 중요.
- **분할을 32GB로 낮추지 말 것** — GPU 천장이 ~26GB로 떨어져 학습이 더 빨리 OOM. **48GB 유지가 정답.**
- **bitsandbytes 4bit는 DirectML에서 불가 → fp16 강제.** 7B=14GB, 14B=29GB.
- DirectML 학습 제약: bf16 미지원(fp16 변환), 단일텐서 ~3GB 한도, gradient checkpointing 역효과,
  HF Trainer 불가(커스텀 루프), PEFT save 실패→어댑터 CPU로 옮겨 직접 저장. 상세 `docs/training-benchmark-7b.md`.

## SCM / Git 룰
- **git pull/push/fetch·gh는 사용자 승인 없이 즉시 수행** (사용자 명시 허가, 2026-06-27).
  계정=genishs(study/ 비대화식). `.claude/settings.local.json` allowlist에 반영됨.
- **금지(deny 유지)**: force-push, `reset --hard`, `git clean`, `rm -rf/-r`.
- 작업 단계마다 **로컬 커밋 계속**. 연관 레포 동시 변경 시 커밋 메시지에 "함께 머지/배포 필수" 명시.
- 수정 후 구동·확인 가이드(.md)는 같은 브랜치에 함께 커밋.

## 8060 ↔ 4060 경쟁 통신 프로토콜 (maildir)
- 8060(이 디바이스, fp16 DirectML) vs 4060(장비#2 shas-sgshs, 4bit CUDA QLoRA) 모델품질 경쟁.
  **통신 = GitHub push/pull** (같은 레포, 4060이 pull로 수신).
- **각 팀은 자기 파일에만 append** (충돌 0):
  - 산문/토론 → `comms/from-8060.md` (우리), `comms/from-4060.md` (상대). **append-only**.
  - 점수 → `comms/scores-8060.jsonl` / `scores-4060.jsonl` (1줄=1측정 JSON). 정본.
  - `docs/competition-log.md`는 과거 내러티브 인덱스(신규 메시지 금지).
- **커밋 메시지 발신 접두**: `[8060→4060]` / `[4060→8060]`.
- 규약 상세 `comms/README.md`. scores 스키마·harness_ver로 동일 기준 대조.
- 채점 하니스: `scripts/eval_hard_tsc.py`(실제 tsc 컴파일, 11하드태스크 + held-out egov 실파일,
  per-file·max_new2048·LF정규화·TS2347 전역제외). 8060 측정용 DML 변형 `eval_harness_dml.py`.
- **교훈(양 노드 독립확증)**: 데이터 양↑ = 분포희석+과적합으로 회귀. 핵심스킬 적정량이 sweet spot.
  진짜 레버 = 용량(+MLP)·품질·정직한 held-out 측정.

## 상시 백그라운드 동기화 (standing loop)
세션 중 `/loop`(자기 페이스)로 주기적 동기화를 가동한다 (사용자 지시, 2026-06-27):
1. `git pull`로 4060 신규 `from-4060.md`/`scores-4060.jsonl` 수신 → 있으면 사용자에게 요약 보고.
2. 학습/측정 결과 발생 시 `from-8060.md` + `scores-8060.jsonl`에 기록하고 `git push`.
3. 진행 없으면 상태만 남기고 대기. push/pull은 자동, **중대·비가역·외부영향 결정만 사용자 확인.**

## 14B fp16 LoRA 재도전 (진행 중, 2026-06-27)
- 39GB 천장 발견으로 재개방(29GB 가중치 < 39GB). Qwen2.5-Coder-14B-Instruct fp16.
- `scripts/dl_14b.py` 다운로드 → `scripts/probe_14b_load.py`로 단계 검증:
  **Stage2** 스트리밍 적재(`src/dml_loader.py:stream_load_to_device`, meta+텐서단위로 5GB 호스트 회피)
  → **Stage3** LoRA 어텐션 r16 + seq128 학습 1스텝. 관문 = 호스트 mmap 로딩 / GPU 잔여 ~10GB.
- 막히면 외장 USB4 디스크 베어메탈 Linux+ROCm(GTT 동적 통합메모리)이 14B+ 정공법
  (내부 디스크·BitLocker 우회). Windows 정적분할은 7B엔 충분, 14B+엔 본질 한계.

## 서빙 (참고)
3경로: CLI `src/inference.py` / FastAPI `src/serve_api.py`(:8000) / MCP `src/mcp_server.py`
(`.mcp.json` 등록, 5툴). 서빙 기본 어댑터·로더는 `src/model_loader.py`. 상세 `docs/mcp-7b-usage.md`.

## 학습 파이프라인
`collect_github_data.py` → `build_dataset_v2.py` → `src/train_directml.py --dtype fp16 --seq N`
(`--lora-r`/`--lora-mlp`/`--smoke` 지원) → `src/inference_7b.py`. config `config/training_config.yaml`.
