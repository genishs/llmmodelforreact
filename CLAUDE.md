# CLAUDE.md — ai_model 프로젝트 운영 룰 (정본)

> 이 파일이 이 프로젝트의 **작업 규칙 정본**이다. (개인 세션 메모리가 아니라 레포에 커밋되어
> 모든 세션·기여자가 공유한다.) 상충 시 이 파일을 우선한다.

> 🔴🔴 **2026-07-16 채점 체계 전복 — 아래 v1 점수를 인용하기 전에 반드시 읽을 것 (양노드 교차검증 5/5 통과)**
> 이 문서 하단(§데이터빌드·§측정)에 나오는 **v1 점수(`score=max(0,1-err/5)`)는 신뢰 불가**로 판정됨. 세 층위로 무너졌다:
> 1. **seed 분산 ±20pp** — 동일 데이터·설정, seed만 바꿔 88.6→68.6. "챔피언 88.6%"는 seed 뽑기였음.
> 2. **백틱 아티팩트** — 안 닫힌 백틱이 파서를 EOF까지 삼켜 에러 은폐 → 더 망가질수록 점수↑(품질과 역상관). r6base medit 0.80의 실체.
> 3. **스텁 과잉보상** — 7B r6base가 테이블을 `{/* ... */}` 주석 스텁으로 뭉갰는데 v1이 0.80(충실 재현한 14B는 0.60). **"7B>14B"·"데이터>크기" 명제 전체가 이 버그의 인공물.**
> **v2 재점수 결과**(양노드 독립 재현, 소수점 일치): 7B 73.8→**69.5**, 14B 61.5→**72.7**(역전). **명제 상태 = "데이터>크기"는 근거소멸, 단 "크기>데이터"도 아님 = "모른다"**(n=2·v2 노이즈 미측정). "14B>7B" 과잉해석 금지.
> **새 채점기 = `scripts/score_v2.py` + `score_v2_extract.cjs`**(구문/타입 분리·충실도축·절단제거, TS컴파일러 API). 과거 원장(`comms/scores-*.jsonl`) 불변, v2는 `scores-*-v2.jsonl` 병기. 상세 = [[eval-harness-untrustworthy]] 메모리 / `docs/project-story-plain-ko.md`(쉬운설명) / `docs/decision-harness-v2-ko.md`(결재). **남은 v2 성숙: ①노이즈 바닥 seed 스윕 ②태스크 7→20 ③배치 디코드.**

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

### ⚡ 배치 디코드 (이슈 #9, 2026-07-30 — 123B/141B 채점 병목 대응, ★실배수 미검증)
- **문제**: 123B heldout7 채점이 batch=1 순차 decode로 20h+ 걸려 5/7 타임아웃(141B는 더 느림).
  `batch_decode_probe.py`(2026-07-16, 샤스 설계)가 배치=N 배수를 재려 작성됐으나 **실행 로그가
  0건** — 만들고 GPU에서 한 번도 안 돌려본 상태였음(2026-07-30 확인).
- **분석**: HQQ 2bit/4bit 디코드는 스텝당 가중치 역양자화가 지배 비용(대역폭 바운드)이고 배치
  크기와 무관 → 배치=N이면 같은 비용으로 스텝당 N토큰. `eval_hard_tsc.py`는 태스크 7개를
  **순차 단일-generate()**로 돌려 이 이득을 전혀 못 쓰고 있었음.
- **실측(123B 토크나이저, GPU 0, 순수 토크나이즈)**: heldout7 입력토큰 = 212~7314 (34배 편차,
  `ho-admin-medit` 최장) → 7개 전부 한 배치는 짧은 태스크에 좌패딩 낭비 + medit의 긴 컨텍스트가
  KV캐시를 배치 전체에 강제해 OOM 위험(123B는 40GB 천장 근처라 여유 얇음).
- **조치**: `scripts/gen_batch_utils.py`(순수 로직: `bucket_by_length`=길이순 그리디 버킷팅,
  `build_prompt`, `trim_generated_at_eos`) + `generate_batch`(배치 1회 generate) 신설.
  `eval_hard_tsc.py`에 `--batch-size`(기본 1=기존과 완전 동일, 회귀 없음)·`--batch-token-budget`
  플래그로 통합. 단위테스트 16개(`scripts/test_gen_batch_utils.py`+`_torch.py`, GPU 0) 전부 PASS.
- **★미검증**: 배치=N의 실제 배수(throughput 배)는 아직 GPU 실측 0건 — 141B 학습 종료 후
  `scripts/batch_decode_probe.py` 먼저 돌려 배수를 재고, 그다음 `eval_hard_tsc.py --batch-size N`
  으로 heldout7 실측할 것. 작게(2~3)부터 시작 — 메모리 여유가 얇다.
- **참고(사이드 발견)**: 이 8060 박스엔 `_resolve_egov()`가 찾는 `egovGeoportal` 경로가 없다 —
  구성요소가 `twinspace_platform/sysadmin-front/src`로 리네임됐음(2026-07 리네임).
  `EGOV_SRC=/mnt/data/Documents/workspace/twinspace_platform/sysadmin-front/src` 지정 필요.

### 🧱 4060 한계 — `ho-admin-medit` 채점은 **8GB 벼랑**이라 비결정적 (2026-07-15 실측)
- **증상**: heldout7 채점이 **traceback도 stderr도 없이 조용히 사망**(OS 킬). 지점이 매번 다르다
  (로딩 중 / mlist 직후 / medit 생성 중). **분리 프로세스(`Start-Process`)로 띄워도 동일** = 하니스 무관.
- **원인(실측)**: 7B 4bit 모델만으로 **GPU alloc 5.33GB / reserved 5.50GB**. Windows 데스크톱이
  **~1.3GB**(explorer·ShellHost) → **여유 ~1.2GB뿐**. `ho-admin-medit`은 입력이 **~10,400토큰**(22KB 파일)이라
  prefill이 GPU를 **7.8 / 8.2GB(95%)**까지 밀어붙인다. **문턱을 오간다 = 성공/실패가 그날 데스크톱 점유에 좌우.**
  (대조: `ho-admin-mlist` 2,114토큰은 안전하게 통과.)
- **∴ medit은 4060에서 "느리지만 된다"** — 죽는 게 아니라 **벼랑에서 스래싱**한다. **WDDM이 GPU 초과분을
  공유 시스템메모리로 스필**하므로 **완주는 하되 극단적으로 느리다**(실측: 분리 프로세스로 **58분+ 생존**,
  GPU 99% 점유 유지). **"측정 불가"가 아니라 "1시간짜리 태스크"로 취급할 것.**
- **★그럼 앞선 3번의 사망은 무엇이었나 = 하니스 백그라운드 태스크가 죽는다.** 같은 커맨드를
  **PowerShell `Start-Process`로 분리**하면 산다. **장시간 GPU 작업은 반드시 분리 프로세스로 띄울 것.**
- **★★ PID 함정(반드시 숙지)**: `venv\Scripts\python.exe`는 **런처 껍데기**다 — 실행 즉시 실제 인터프리터
  (`...\Python311\python.exe`)를 **자식으로 띄우고 자신은 CPU 0으로 남는다**. `Start-Process`가 돌려주는 PID는
  **껍데기 PID**이므로, **그걸 감시하면 작업이 살아있는데도 "죽었다"고 오판한다**(실제로 겪음).
  **진짜 PID 찾기**: `Get-CimInstance Win32_Process -Filter "ParentProcessId = <껍데기PID>"` 또는
  `Get-Process python | ? { $_.CPU -gt 0 }`. **CPU 시간이 도는 쪽이 진짜다.**
- **⚠️ GPU 점유 확인 후 겹쳐 던지지 말 것**: `nvidia-smi --query-compute-apps`는 권한 부족으로 `[N/A]`만
  보여줘 **누가 GPU를 쥐었는지 안 보인다**. `--query-gpu=memory.used,utilization.gpu`로 **총량·사용률**을 보라.
  **7GB+/99%면 누군가 쓰는 중**이다(실제로 medit이 쥔 GPU에 학습을 겹쳐 던져 즉사시킴).
- **⚠️ medit 제외의 대가**: cap384→1024 델타가 **17.2pp → 6.7pp로 쪼그라든다**(medit이 +0.8로 최대 기여자).
  **6태스크 부분측정은 사실상 admin-dae 하나에 의존** → 결론을 medit 없이 세우지 말 것.
- **처방**: ①**`scripts/score_saved_dml.py --label <라벨>`로 오프라인 채점**(GPU 불필요) — 하니스가 생성물을
  `eval_results/gen/`에 영구보존하므로(`eval_hard_tsc.py:262`) **죽어도 완료분은 건진다.** `--exclude`로 태스크 제외.
  ②**medit은 8060(50GB)에 위탁**하는 게 맞다 — 어댑터(161MB)를 넘기면 그쪽은 여유롭게 돈다.
- **⚠️ 진단 시 주의**: 죽을 수 있는 프로세스의 출력을 `| grep`/`| tail`로 파이프하면 **버퍼링 때문에 사망 시
  로그가 통째로 유실**된다(실제로 겪음). **파일로 직접 리다이렉트**하고 나중에 읽을 것.
- **부분측정 등록 규칙**: `pct`는 **측정한 태스크 수를 분모로** 하고 `partial:true`·`excluded_tasks`를 명시.
  **7태스크 점수와 직접 비교 금지**(분모가 다름) — 반드시 **같은 태스크 집합끼리** 비교할 것.
  (예: ablation 86.7%(6) vs r6base **90.0%(동일 6)** — 88.6%(7)와 비교하면 오독.)

- **데이터는 양이 아니라 커버리지**: 짧은 합성 스킬 10개 추가(r6admin) = **-14.3pp 회귀**,
  긴 실파일 9개 = **+17pp**. **"타깃 스킬을 짧게 만들어 넣기"는 이미 실패했다.**
  새 데이터는 **소량·긴 실파일 형태**로, **대조군과 동시 측정**할 것.
