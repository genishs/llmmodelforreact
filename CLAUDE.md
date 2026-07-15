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

### ⚙️ 머신 셋업 — 권장 allowlist (다른 위치/장비에서 동일 룰 적용용)
`.claude/`는 gitignore(머신별 토큰·경로) → 설정 파일 자체는 push 안 됨. **새 장비에서 이 프로젝트를
무인 자동화로 돌리려면** 아래를 그 장비의 `.claude/settings.local.json`에 복사하고 `gh auth login`만
하면 된다(토큰은 keyring 로컬 저장, 레포에 안 들어감). 이 블록이 8060 설정의 **공유 정본**이다.
```jsonc
{ "permissions": {
  "allow": [
    "Bash(./venv/Scripts/python.exe:*)",          // 학습/추론/다운로드 실행
    "Bash(git fetch:*)","Bash(git pull:*)","Bash(git push:*)","Bash(gh:*)",
    "Bash(git add:*)","Bash(git commit:*)","Bash(git status:*)","Bash(git log:*)",
    "Bash(git diff:*)","Bash(git branch:*)","Bash(git remote:*)","Bash(git stash:*)",
    "Bash(tee:*)","Bash(echo:*)","Bash(nohup:*)","Bash(kill:*)","Bash(ps:*)","Bash(date:*)",
    "Bash(cat:*)","Bash(tail:*)","Bash(head:*)","Bash(ls:*)","Bash(find:*)",
    "Bash(grep:*)","Bash(wc:*)","Bash(du:*)","Bash(cp:*)","Bash(sleep:*)","Bash(mkdir -p logs)"
  ],
  "deny": [                                          // approval-deputy의 HOLD와 동일 — 절대 자동실행 금지
    "Bash(git push --force:*)","Bash(git push -f:*)","Bash(git push --force-with-lease:*)",
    "Bash(git reset --hard:*)","Bash(git clean:*)","Bash(rm -rf:*)","Bash(rm -r:*)","Bash(rmdir:*)"
  ],
  "enabledMcpjsonServers": ["react-assistant"]
} }
```

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

## 자동화 페르소나 & 백그라운드 에이전트 (2026-06-27 사용자 지시)

### approval-deputy (승인 대행 페르소나)
사용자 부재 중 권한 요청을 **감지·대신 처리**한다. 사용자 확약: *"필요시 내가 인터럽트를 걸도록 할께."*
- **자동 승인(AUTO)** — 안전작업 전부 + **학습/통신 전부**:
  git pull/push/fetch·gh(읽기/PR/이슈 조회), 로컬 커밋, 14B/7B **학습 실행**, eval 측정,
  comms append+push, 다운로드/재시도, 파일 read/grep/edit. → 권한창 없이 즉시 진행.
- **보류(HOLD) → 사용자 확인 필수**: force-push, `reset --hard`, `git clean`, `rm -rf/-r`,
  **외부 영향**(새 public repo 생성, 이슈/PR 공개 게시, 외부 유료 API 호출, 비밀 노출).
- 보류건은 큐에 모아 한 번에 요약 보고. 사용자가 인터럽트로 중단·수정 가능.

### github-sync (주기 동기화 에이전트)
CronCreate로 **세션 중 4분마다(≤5분 보장)** 자동 가동 (durable=false, 세션 종료 시 정지·재무장).
gh 인증=genishs(repo scope, keyring) → **별도 인증 없이** push/pull. 매 사이클:
1. `git pull` → 4060 신규 `from-4060.md`/`scores-4060.jsonl` 있으면 사용자에게 **요약 보고**.
2. 8060 학습/측정 결과 발생 시 `from-8060.md`+`scores-8060.jsonl` append → `git push`.
3. 14B 다운로드 진행/완료 감지 시 보고. 진행 없으면 1줄 상태만, 조용히 대기.
4. push/pull은 자동, **HOLD 항목만 사용자 확인.** 충돌·force 필요 시 절대 강제 안 함→보고.

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
`collect_github_data.py` → `build_dataset_v2.py` → **학습 스크립트 2종 중 택1**(↓) → `src/inference_7b.py`.
config `config/training_config.yaml`.

### ⚠️ 학습 스크립트는 2종이다 — 헷갈리면 OOM (2026-07-15 실측으로 정정)
| 스크립트 | 백엔드 | 4bit | 용도 |
|---|---|---|---|
| **`src/train_qlora.py`** | CUDA | **O**(BitsAndBytesConfig nf4) | **4060(8GB)의 모든 r4~r6 어댑터 = 이것.** 8GB엔 이것만 가능 |
| `src/train_directml.py` | DirectML / CUDA / ROCm | **X**(fp16·bf16 전용) | 8060 트랙(DirectML 커스텀루프 → ROCm 이중백엔드) |

- **4060 정본**: `python src/train_qlora.py --seq 768 --rank 16 --target qkvo_mlp --out <경로>`
  (인자: `--config --seq --out --rank --alpha --target{qkvo,qkvo_mlp} --epochs --base --max-steps`)
- **8060 정본**: `python src/train_directml.py --backend {directml,cuda,auto} --dtype {fp16,bf16} --seq N`
  (`--lora-r`/`--lora-mlp`/`--smoke`/`--train-file`/`--base`/`--epochs`/`--optim` 지원)
- **`train_directml.py`로 4060 어댑터를 재현하면 fp16 7B(14GB)가 8GB에 안 들어가 OOM**한다
  (`ForCausalLMLoss`의 `logits.float()`에서 폭사, "22.20 GiB is allocated"). 실제로 겪었다.
  단서는 `comms/scores-4060.jsonl`의 `base: "4bit"` — **어댑터가 4bit면 `train_qlora.py`다.**

### ⚠️ config 함정 2개
1. **`train_qlora.py`엔 `--train-file`이 없다** — 학습셋은 `cfg["data"]["train_file"]`에서 읽는다.
   다른 데이터로 돌리려면 **config 사본을 만들어 `--config`로 넘길 것**(예: `config/training_config_r7abl.yaml`).
   (`train_directml.py`엔 `--train-file`이 있다 — 이것도 두 스크립트의 차이.)
2. **config의 `fp16: false`·`gradient_checkpointing: false`는 스크립트가 런타임에 덮어쓴다**
   (실제 `training_args.bin`엔 둘 다 `True`). **config 파일만 보고 학습 조건을 판단하지 말 것** —
   정본은 `models/*/checkpoint-*/training_args.bin`이다.

### 데이터 빌드 — `--cap`이 최대 레버 (2026-07-15 규명)
- `build_dataset_v2.py --cap N --gh-out-cap M`. **`--cap`은 출력상한이 아니라 alpaca 전체 프롬프트 토큰 상한.**
- **기본값 `--cap 384`는 `handcrafted_synth_egovreal.jsonl`(실제 egov 파일 변환) 10쌍을 0개 채택한다**(전부 384 초과).
  그런데 **held-out 평가는 전부 실제 egov 파일 변환**이다 → **평가 스킬의 교재를 0개 받고 시험을 보게 된다.**
  이것 하나가 **r4mlp 71.4% → r6base 88.6% (+17.2pp)** 의 전부였다(나머지 변인은 `training_args.bin` 전 필드 diff로 배제).
- **r6base 재현**: `python src/build_dataset_v2.py --cap 1024 --gh-out-cap 512` → **351개(315/36)**.
  **r4mlp 재현**: 무플래그(=cap384) → 283개(254/29).
- 빌더 구조: `SYNTH_GLOB="./data/handcrafted_synth*.jsonl"`만 글롭한다. `HANDCRAFTED_QA`는
  **`src/build_dataset.py:17`의 코드 상수**(파일 아님). **`.bak`는 글롭에서 빠져 봉인 상태**(round5·admin_round6).

### 측정 — 판정은 held-out 점수로만, **val_loss로 하지 말 것**
- 캐논: `python scripts/eval_hard_tsc.py --adapter <경로> --label <이름> --heldout --max-new 4096`
  (harness_ver `HELDOUT7-mn4096-lf-PERFILE-noTS2347`, `--base`/`--base-load{4bit,bf16,fp16}` 지원).
- **val_loss는 일반화와 역행한다(실측)**: r4mlp `eval_loss 0.3853`(더 낮음) → **71.4%** /
  r6base `0.4096` → **88.6%**. **loss 곡선이 예쁜 걸 성공 신호로 읽지 말 것.**
- **데이터는 양이 아니라 커버리지**: 짧은 합성 스킬 10개 추가(r6admin) = **-14.3pp 회귀**,
  긴 실파일 9개 = **+17pp**. **"타깃 스킬을 짧게 만들어 넣기"는 이미 실패했다.**
  새 데이터는 **소량·긴 실파일 형태**로, **대조군과 동시 측정**할 것.
