# React 코드 어시스턴트 — 학습 소스코드 확보 방안

- 작성: 앜선생 (system-architect), 2026-08-29
- 요청: 두목 → PM(피선생) → 앜선생
- 질문: "리액트 코드 어시스트를 만들기 위해 사용할 소스코드를 조금 더 확보해두는 것은 어떤가?"
- 원칙: 조사·설계만. 대용량 다운로드는 실행하지 않음. 두목이 결정.

---

## 0. 결론 먼저 (TL;DR)

| 질문 | 답 | 근거 |
|---|---|---|
| 지금 모델이 "코딩 실력 부족"인가 "우리 관례만 배웠는가"? | **둘 다 아니다 — 이미 대조군 실험으로 확인됨.** LoRA 없는 base 모델도 heldout7에서 짧은 태스크는 fidelity 0.99~1.0으로 잘 풀었다(코딩 실력 자체는 있음). 무너진 건 admin 폼·22KB급 장문처럼 **길고 복잡한 케이스에서 응답 생성 자체가 0~10자로 끊기는 것**뿐이었다. 그리고 그 문제를 지금의 **351건짜리 소량 자체 코퍼스가 이미 20.0%→64.9~70.5%로 크게 줄여놓았다**(§1-1, 실측). | §1-1 |
| 그럼 범용 React 코퍼스를 대량으로 넣어야 하나? | **아니다. 이 파이프라인에서 데이터 양 증가는 3전 3패로 반복적으로 회귀를 냈다(실측)**, 게다가 이미 작은 코퍼스로 3배 이상 개선을 낸 뒤라 한계효용도 낮다. | §2 |
| 그럼 뭘 해야 하나? | **실패 태스크가 지목하는 특정 스킬(제네릭·null-safety·import보존 등)을 겨냥한 소량 고품질 예제를 계속 추가** — 지금 하고 있는 방식을 유지 | §5 |
| 외부 공개 React 코퍼스는 아예 필요 없나? | **완전 불필요는 아니다.** 이미 소량(MIT 라이선스 9개 레포, 41/315건) 쓰고 있고, "실패 스킬 패턴"을 지닌 예제를 더 뽑아오는 정밀 확장은 유효 — 단 대량 스크레이핑이 아니라 **표적 소량 추가** | §3, §5 |
| 지금 당장 할 일인가? | **아니다.** 현재 병목은 데이터가 아니라 **평가/채점 인프라**(배치디코드, 대형모델 heldout 채점) — CLAUDE.md·progress 문서가 이미 이렇게 결론 냄 | §5-D |

---

## 1. 분기 판단 — "코딩 실력 부족" vs "관례만 학습" (요청받은 핵심 분기)

두목이 제기한 우려("EgovSelect, @/constants/url 같은 우리 관례만 가르치는 것 아니냐")는 정당한 의심이지만,
이 프로젝트에는 **이미 그보다 더 구체적인 실측 결과**가 있다. `comms/error-taxonomy.md`, `comms/from-4060.md`,
`docs/model-training-history.md`, `comms/distill/README.md` 4곳이 교차 확인하는 사실:

1. **"데이터 양을 늘리면 개선된다"는 가설은 이미 여러 라운드에 걸쳐 반증됐다.**
   - r6admin(관례 패턴 10개 추가) → held-out **−14.3pp 회귀**.
   - "데이터 양 증가 = 분포 희석 + 경미한 과적합"(`from-4060.md:288`), eval_loss가 epoch2→3에 오히려 상승.
   - 풀페이지 실파일 변환(admin 6파일, 1.2K~4.2K 토큰)을 그대로 학습에 넣었더니 seq768 학습창을 초과해
     **학습에 해로움**으로 판정 → 투입 금지, "짧은 패턴 스킬 추출 소스"로만 격하(`comms/distill/README.md`).
   - `docs/model-training-history.md` 핵심교훈 #3: "데이터는 양이 아니라 품질·구성... 데이터量↑=희석."
   - 이 반증은 **두 노드(4060 CUDA / 8060 ROCm·DirectML), 여러 체급(7B~123B)을 가로질러 재현**됐다 —
     노이즈가 아니라 이 파이프라인의 구조적 특성이다.

2. **실패 유형(tsc 에러) 자체는 "우리 관례"가 아니라 일반 TypeScript/React 스킬이다.**
   `comms/error-taxonomy.md`에 정리된 공통 약점: import 보존(TS2304), 제네릭 타이핑(`keyof T`, `T[K]`),
   `React.FC` + children(React18), null-safety(TS18047/18048), 함수 인자수(TS2554), `.tsx` 제네릭 파싱
   모호성(`<T,>`). **전부 일반 TS/React 능력 문제이지, "EgovSelect라는 이름을 모른다" 류의 관례 문제가
   전혀 아니다.** 즉 두목의 우려("관례만 배웠다")는 이 taxonomy 기준으로는 **기각**된다 — 모델이 부족한 건
   진짜 TS 스킬이다.

3. **그런데 그 스킬 부족을 고친 방법은 "범용 React 코드 대량 투입"이 아니라 "그 스킬 하나를 겨냥한
   6~30줄짜리 합성 예제 소량"이었다.** round4(제네릭 11쌍+import보존 8쌍), round5(import보존 24쌍),
   round7(재현성 검증 후 1개 스킬만 3쌍 추가) — 전부 **직접 작성한 IP-clean 합성 코드**이지 GitHub
   스크레이핑이 아니다. 이 방식이 "held-out 최대 레버"로 검증됐다(`round4_manifest.md`).

**결론**: 질문이 이분법("관례 vs 실력")으로 던져졌지만, 답은 그 둘의 교차점에 있지 않고 **제3의 축(양 vs
표적 품질)에서 이미 판가름 났다.** 실력 부족은 맞지만, 그 처방은 대량 범용 코퍼스가 아니라 실패
패턴을 정조준한 소량 고품질 합성 데이터다. 이는 두목이 예상한 두 가설(A: 관례만 학습 → 소량 고품질 필요,
B: 범용 실력 부족 → 대량 필요) 중 **결과적으로 A와 같은 처방(소량 고품질)에 도달하지만, 이유는 다르다**
— "관례라서"가 아니라 "이 학습 파이프라인 자체가 양에 민감하게 반응해서"다.

### 1-1. 직접 대조군 실험 (base vs LoRA, 같은 채점기) — 이번 조사에서 새로 확보한 결정적 증거

`eval_results/7b-BASE-noLoRA-q8-mn4096.json`은 LoRA를 전혀 얹지 않은 베이스 모델의 heldout7 생성
결과였는데, 지금까지 채점(scoring)만 안 된 채로 남아 있었다. 이번 조사 과정에서 기존 `scripts/score_v2.py`로
직접 채점해(다운로드·재생성 없음, 이미 있는 산출물에 대한 순수 분석 실행) `comms/scores-4060-v2.jsonl`에
결과를 남겼다:

| 모델 | heldout7 v2 점수 | 비고 |
|---|---|---|
| **base, LoRA 無** | **20.0%** | 7태스크 중 3개(select/gallery/attachfile)는 fidelity 0.99~1.00으로 응답 품질 자체는 좋음. 나머지 4개(about-org/admin-dae/admin-mlist/admin-medit)는 생성 글자수가 **0~10자** — 타입에러가 아니라 응답 생성 자체가 무너짐 |
| **r4mlp (351건 자체 코퍼스로 학습한 LoRA)** | **64.9%** | 동일 하니스 |
| r4mlp, llamacpp q8 재측정 | **70.5%** | 동일 하니스, 다른 실행 경로 |

**해석**: base 모델이 "React/TypeScript 자체를 못 쓴다"(순수 실력 붕괴)는 아니다 — 답을 낸 곳에서는
이미 준수한 품질이었다. 진짜 약점은 **admin 폼·22KB급 장문처럼 길고 복잡한 케이스에서 응답 생성이
끊기는 것**(`error-taxonomy.md`가 이미 별도로 지목한 "admin 도메인 일반화"·"초장문 생성완결"과 동일
패턴)이었고, 이걸 지금의 **351건짜리 소량 코퍼스가 이미 3배 이상(20.0%→64.9~70.5%) 개선**해놓은
상태다. 즉 "코퍼스가 작아서 못 고친 문제"가 아니라 **이미 작은 코퍼스가 상당 부분 고친 문제**이고,
남은 잔차가 admin/장문 케이스에 몰려 있다 — 대량 범용 코퍼스로 공략할 성질이 아니라 §1의 처방(표적
소량)이 맞는 이유가 대조군으로도 확인된다.

---

## 2. 현행 코퍼스 실측 (추정 아님, 코드로 확인)

### 2-A. 평가(eval) 소스 — 실측, 두목 말대로 정말 단일 소스

| 항목 | 값 | 실측 방법 |
|---|---|---|
| 트리 | `twinspace_platform/sysadmin-front/src` (구 `egovGeoportal`, 2026-07 리네임 — `EGOV_SRC` 환경변수로 참조하는 바로 그 트리) | `scripts/eval_hard_tsc.py`, `scripts/score_v2.py` 코드 확인 |
| .jsx 파일 수 | **84개** | `find ... -name "*.jsx" \| wc -l` |
| .tsx 파일 수 | **0개** | 동일 — 소스가 100% 레거시 JSX, TS 마이그레이션 전 |
| .js 파일 수(유틸 등) | 17개, 735줄 | 동일 |
| 총 라인수(jsx+js) | **14,725줄** (jsx만 13,990줄) | `wc -l` |
| 평가 태스크로 쓰이는 파일 수 | heldout7(7) + core16(16) + canary4(4) + xl3(3, 1개는 heldout과 중복) = **실질 29개 고유 파일** | `comms/v2-proposal/tasksets_v2.json` |

**중요 정정**: PM 지시문의 "학습 데이터의 출처는 사실상 하나(sysadmin-front/src)"는 **평가(채점) 기준으로는
정확하지만, 학습(training) 데이터 기준으로는 부정확하다.** 아래 2-B 참조.

### 2-B. 학습(training) 소스 — 실제로는 "합성 위주 + 소량 실파일 + 소량 공개GH"의 혼합

`src/build_dataset_v2.py`가 현재 정본 파이프라인(v1은 `.orig` 백업으로만 존재, 84건 → v2가 351건으로 확장).

| 구성 요소 | 파일 | 건수 | 성격 | 라이선스/IP 상태 |
|---|---|---|---|---|
| 핸드크래프트 합성 (round1~7 + admin round6) | `data/handcrafted_synth*.jsonl` 등 8개 파일 | 305건 (원본 raw, cap 필터 전) | **직접 작성**, 매 라운드 매니페스트에 "외부 회사 소스 미사용" 명시 | 자체 저작 — 클린 |
| 실파일 기반 변환쌍(큐레이션) | `data/handcrafted_synth_egovreal.jsonl` | 10건 | 실 eGovFrame 템플릿 파일명·구조를 참고해 **직접 재작성**한 출력(입력은 build_egov_pairs.py 안에 인라인, eval 대상 2파일은 제외) | eGovFrame 표준 템플릿 페이지로 보임(§4 참고), 확인 필요 |
| GitHub 공개 수집 | `data/raw/github_react_qa.jsonl` | 74건 raw → 큐레이션 후 **41건이 실제 최종 train에 채택** (315건 중 13%) | bulletproof-react, zustand, Next.js examples, shadcn/ui, recharts, TanStack Query, redux-toolkit, jotai, react-spring | **전부 MIT 확인**(§3-A) |
| 최종 학습/검증 | `data/processed/react_train.jsonl` / `react_val.jsonl` | **315 / 36** (90/10 split, seed 42) | cap=384 토큰(전체 프롬프트), gh_out_cap=200 토큰(GH 출력) | — |

**형식**: Alpaca 스타일 단일 `text` 필드(`### Instruction / ### Input / ### Response`). 태스크 유형은
거의 전부 "짧은 컴포넌트/훅 작성" 또는 "JS→TS 변환(props를 interface로, 이벤트/상태 타입 명시)".

**heldout 7건**: `EgovSelect.jsx`, `EgovImageGallery.jsx`, `EgovAboutOrganization.jsx`, `EgovAttachFile.jsx`,
`EgovAdminDataAccessEdit.jsx`, `EgovAdminMemberList.jsx`, `EgovAdminMemberEdit.jsx` — sysadmin-front/src
실파일 중 "불변 앵커"로 고정, 학습 데이터에서 3중 오염가드(`guard_eval_leak.py`)로 원천 차단.

**총 데이터 디렉토리 용량**: 1.9MB (전부 텍스트 jsonl, 규모 자체가 매우 작다).

### 2-C. TS/TSX 비율 요약

| 소스 | 파일 수 | TS/TSX 비율 |
|---|---|---|
| sysadmin-front/src (eval 트리) | 84 jsx | **0%** — 전량 레거시 JSX |
| 학습용 합성 데이터 | 351건 | 100% — 전부 TS/TSX 출력을 목표로 작성됨(가르치는 대상이 JS→TS 변환이므로) |

이 비대칭(입력은 100% JS, 학습목표 출력은 100% TS)이 프로젝트의 본질이다 — "실제로 존재하는 TS 코드"를
어디서도 대량으로 보고 배우는 게 아니라, **"어떻게 TS로 잘 옮기는가"를 사람이 큐레이션한 예제로 가르치는
구조**다. 이 구조를 이해하지 않고 외부 TSX 코퍼스를 넣으면 목표(변환 스킬)와 어긋날 수 있다(§5 참고).

---

## 3. 외부 확보 경로 조사

### 3-A. 이미 쓰고 있는 경로 — GitHub 공개 API 직접 수집 (저비용, 이미 검증됨)

`src/collect_github_data.py`가 인증 없이 GitHub Contents API로 아래 9개 레포에서 수집 중:

| 레포 | 라이선스(웹 확인) | 비고 |
|---|---|---|
| alan2207/bulletproof-react | **MIT** | 실무형 아키텍처 예제 |
| pmndrs/zustand | **MIT** | 상태관리 |
| vercel/next.js (examples/*) | **MIT** | 공식 예제 |
| shadcn-ui/ui | **MIT** | shadcn/ui, "copy-paste" 컴포넌트 배포 방식 자체가 학습데이터로 최적 |
| recharts/recharts | **MIT** | 차트 |
| TanStack/query | **MIT** | 데이터 페칭 |
| reduxjs/redux-toolkit | **MIT** | 상태관리 |
| jotaijs/jotai | **MIT** | 상태관리 |
| pmndrs/react-spring | **MIT** | 애니메이션 |

**전부 MIT — 라이선스 리스크 없음.** 이미 좋은 선택을 했다. 다만 §2-B에서 보듯 74건 raw 중 41건만
채택됐고(짧은 지시문에 거대한 원본 소스가 매핑되는 문제로 대부분 탈락), 학습 전체의 13%에 불과 —
**이 경로를 확장하려면 레포 목록을 늘리는 것보다 `collect_github_data.py`의 수집 단위를 "파일 전체"가
아니라 "함수/컴포넌트 단위로 쪼개서 지시문과 크기를 맞추는" 방향이 더 효율적**(현재 탈락 사유가
"출력이 cap 초과"이므로 원천에서 더 잘게 자르면 채택률이 오른다).

### 3-B. 대량 코퍼스 — HuggingFace `bigcode/the-stack` 계열

| 데이터셋 | 전체 크기 | 라이선스 필터링 | TS/TSX 특이사항 |
|---|---|---|---|
| `bigcode/the-stack` (v1) | 3.1TB, 30개 언어 | permissive만 (레포 단위 라이선스 감지) | TypeScript는 "permissive 비율이 평균(10%)보다 낮은 4%" — 상대적으로 데이터가 적음 |
| `bigcode/the-stack-smol` | **2.6GB** (언어당 1만 샘플 랜덤) | 위와 동일 상속 | 언어당 균등이라 TS/TSX 몫은 수십~수백MB 추정(실측 아님) — 소규모 파일럿용으로 적합 |
| `bigcode/the-stack-v2` | 67.5TB(중복제거 32.1TB, ~900B 토큰) | Blue Oak Council 승인 + ScanCode permissive/public-domain만. **opt-out(takedown) 메커니즘 있음** | 언어별 필터링 가능(658개 언어). **주의: 기본 배포본은 메타데이터(427GB)뿐 — 실제 파일 본문은 별도로 Software Heritage/S3에서 콘텐츠를 받아와야 함(2단계 파이프라인 필요, 엔지니어링 비용 존재)** |
| `nuprl/the-stack-ts` | 미상(the-stack 파생, TS만 사전 필터) | the-stack 상속(라이선스 다양, "귀속 조항 포함 준수 필요"로 명시) | **Gated 데이터셋**(HF 계정으로 접근 동의 필요), 2021-12-31 이전 파일만(그 이후는 평가용으로 별도 예치) |

**부수 발견(이번 조사 범위 밖, PM에 별도 티켓 권장)**: `src/collect_github_data.py`의 REPOS 목록에는
`jotaijs/jotai`로 적혀 있으나 GitHub 조직명이 `pmndrs/jotai`로 바뀌었거나 원래 오기였을 가능성이 있어
(`gh api repos/jotaijs/jotai` 404 확인) — 이 경로가 지금도 조용히 수집 실패하고 있을 수 있다. 이번
임무 범위는 아니므로 수정하지 않았지만, 기존 파이프라인의 "조용한 손실"이라 별도로 알린다.

**라이선스 판단**: the-stack 계열은 "permissive 라이선스만" 표방하지만 **파일 단위가 아니라 레포 단위
감지**이고, "귀속 조항이 있는 라이선스도 포함될 수 있다(attribution clauses when relevant)"고 스스로
명시한다. 즉 **MIT/Apache-2.0처럼 명확한 게 섞인 걸 그대로 학습에 넣으면 개별 파일 출처를 잃어버려
귀속 의무를 못 지킬 위험**이 있다 — "아마 괜찮다"로 넘길 수 없는 지점. 쓰려면 최소한 라이선스 CSV
메타데이터를 같이 받아 MIT/Apache-2.0/BSD 등 **귀속 조항 없는 서브셋만 다시 필터링**해야 안전하다.

**용량·시간 현실성**: `the-stack-smol`(2.6GB)은 디스크·시간 부담이 사실상 없다(외장 어디든 즉시 가능,
다운로드 분 단위). 반면 `the-stack-v2`에서 TS/TSX만 제대로 추출하려면 (a) 언어 필터 쿼리 + (b) 콘텐츠
블롭 별도 다운로드 + (c) 라이선스 재필터링 3단계 파이프라인을 새로 구축해야 하며, 이는 **디스크 용량
문제가 아니라 순수 엔지니어링 공수 문제**(추정 1~2인일, 실측 아님).

### 3-B'. 대안 — `codeparrot/github-code` (파일 단위 라이선스 필터, the-stack보다 정밀)

the-stack 계열의 "레포 단위 라이선스 추정"이 불안한 대안으로, `codeparrot/github-code`는 **파일 단위
라이선스 메타데이터**를 갖고 있어 `load_dataset(..., licenses=["mit","apache-2.0"], languages=["TypeScript"])`
형태로 **로드 시점에 언어+라이선스를 동시에 필터링**할 수 있다. 원본은 115M 파일/873GB 규모이지만
스트리밍 + 필터로 필요한 만큼만(예: 수만 파일) 받으면 되므로 the-stack-v2의 "메타데이터/콘텐츠 2단계
다운로드" 같은 추가 공수가 없다. **TypeScript 언어 필터가 the-stack보다 명시적으로 잘 지원**되므로,
굳이 대량 코퍼스를 시도하게 된다면 the-stack-v2보다 이쪽이 엔지니어링 비용이 낮다(단, 이번 조사에서
직접 접속·용량 실측은 안 함 — 필요시 착수 전 재확인 필요).

### 3-C. 큐레이션된 고품질 레포 — 개별 클론

shadcn/ui, Next.js `examples/`, TanStack 예제, bulletproof-react 등은 이미 §3-A에서 API로 수집 중이므로
**레포 전체를 별도로 클론하는 것은 API 수집과 중복**이다. 추가로 고려할 만한 후보(라이선스 미확인 —
쓰기 전 반드시 개별 확인 필요):
- `shadcn-ui/next-template`, Vercel `commerce` 계열 — 확인 필요
- Cal.com, Supabase 대시보드류 실무 코드는 **AGPL/상용 라이선스가 섞여 있어 위험군** — 이번 조사에서
  라이선스 확인 안 함, 후보에서 제외 권고

### 3-D. 디스크·시간 현실성 총괄

| 옵션 | 예상 용량 | 예상 다운로드 시간(현재 회선 미실측 전제) | 디스크 여유 대비 |
|---|---|---|---|
| GH API 확장 수집(레포 추가/재수집) | <100MB | 분 단위 | 문제 없음 |
| the-stack-smol | 2.6GB | 분 단위 | 문제 없음(모든 디스크에 여유 충분) |
| the-stack-v2 TS만(메타+콘텐츠, 추정) | 수십~수백GB(실측 안 됨 — 파일 수 확인 전 추정 불가) | 수 시간~ | 8TB(2.8T 여유)나 NVMe(1.3T 여유)면 가능하나, **엔지니어링 착수 전 정확한 용량조차 모른다** |

---

## 4. 이 장비에 이미 있는 자산 — 로컬/외장 디스크 조사

### 4-A. 로컬 `/mnt/data/Documents/workspace/` 자산 (실측)

| 경로 | 업무/개인 | jsx+tsx 파일 | 총 라인수 | 라이선스 | 비고 |
|---|---|---|---|---|---|
| `twinspace_platform/sysadmin-front/src` | 업무 | 84 (jsx만, tsx 0) | 13,990 | LICENSE=Apache-2.0(§4-C 참고) | 현재 학습·평가의 본체(§2) |
| `twinspace_platform/sysadmin-front-r7fix/src` | 업무 | 84 | 13,990 | 동일 | **sysadmin-front와 파일수·라인수 완전 동일 — 신규 자산 아님(fix 브랜치 워킹카피)** |
| `twinspace_platform/geoweb` | 업무 편입, **업스트림 오픈소스**(TerriaJS 기반 모노레포, `@twinspace/geoweb-monorepo`) | **467** | **70,729** | **Apache-2.0**(LICENSE.md 실측 확인) | sysadmin-front보다 5배 이상 큰 React/TS 소스가 이미 이 장비에 있음. 다만 대부분 TerriaJS 업스트림 코드 + TwinSpace 델타가 섞여 있어 "우리 관례" 신호는 옅고, 지도/3D 뷰어 도메인이라 React 코드 어시스턴트가 목표로 하는 관리자 폼/목록 패턴과도 거리가 있음 — 후보이긴 하나 우선순위 낮음 |
| `twinspace_platform/ugfacility_pr/src` | 업무 | **32 (전부 .tsx/.ts, jsx 0)** | 7,950 | 사내 | **TS 네이티브로 유일하게 볼륨 있는 사내 자산.** sysadmin-front는 100% 레거시 JSX라 "우리 팀이 실제로 짠 TSX"가 이 코퍼스 밖엔 사실상 없다 — 관례 학습 관점에서 sysadmin-front보다 오히려 이게 더 직접적인 정답 소스일 수 있음(§5 권고 반영) |
| `study/egovframe-template-simple-react/src` | **공개(eGovFrame 정부 표준 템플릿)** | 77 jsx + 12 js = 89 | 13,074 | **Apache-2.0**(LICENSE 실측), package.json에 `react ^18.3.1` 확인 | eval에서 "다른 템플릿, 절대 아님"으로 이미 분리돼 있어 오염 위험 낮음. sysadmin-front와 같은 eGovFrame 관례 계열이면서 라이선스가 깨끗함 |
| `study/ai-trader` | 개인 | 55 | 15,599 | 없음(두목 개인 저작 — 소유자 본인 사용은 라이선스 문제 아님) | `apps/web` 하위, react ^19.2.0 확인 |
| `study/biklonz` | 개인 | 33 (전부 tsx) | 3,563 | 없음(개인 저작) | `recreate/client`, `recreate/admin` 하위, react ^18.3.1 확인 |
| `study/subway-map` | 개인 | 6 | 480 | 없음(개인 저작) | |
| `study/my-webgis` | 개인 | 2 | 132 | 없음(개인 저작) | 소량, 영향 미미 |
| `study/reactasist` | — | 0 | 0 | — | **이름과 달리 React 프로젝트 아님**(Python `.venv` 확인 — 이름만 보고 넘겨짚지 말라는 원칙대로 직접 확인함) |
| `study/npu-web-demo`, `wbml_web`, `dh2-py-editor`, `snakegame`, `defensegame`, `wonderboy`, `moltbook`, `sharepoi-sgshs` | 개인 | 0 | 0 | — | package.json에 react 의존성 없음 확인 — React 프로젝트 아님 |
| `twinspace_platform/extapi`, `egovUgfacility` | 업무 | 0 | 0 | — | 프론트 소스 없음(백엔드/설정 위주로 확인) |
| `twinspace_platform/gumi-sso` | 업무 | 1 | 16 | — | 소량, 영향 미미 |

### 4-B. 외장 디스크 3개 자산 (실측 — 새 소스 없음)

| 디스크 | 내용 | 판정 |
|---|---|---|
| `/run/media/user/새 볼륨`(2TB, 여유 719G) | `ai_model`(모델 체크포인트 백업), `workspace/claude-agent-team`(이 레포 백업), `bak/` | 코드 소스 아님 |
| `/run/media/user/sgshs_data`(2TB NVMe, 여유 1.3T) | `Documents/workspace/`에 `study/egovframe-template-simple-react`, `study/reactasist`, `twinspace_platform/...` 등 | **mini 장비 workspace의 구버전 미러**(메모리 `device-mini.md` 계열과 일치) — `/mnt/data`와 동일 내용의 중복 사본, 신규 자산 아님 |
| `/run/media/user/data`(8TB, 여유 2.8T) | `mini-sgshs/Desktop`(개인 바탕화면 백업), 3D 타일/GIS 데이터, 가상머신 이미지 위주 | React/TS 소스 없음 |

**→ 외장 디스크 3종은 "새로 확보할 소스"가 아니라 "확보한 걸 놓아둘 자리"(총 여유 약 4.8TB)로만
유효하다.** §3-B(the-stack-v2 등)를 실제로 시도하게 된다면 다운로드 목적지로 8TB 디스크(2.8T 여유) 또는
NVMe(1.3T 여유)를 쓰면 된다 — 디스크 공간은 병목이 아니다.

### 4-C. 업무 vs 개인 구분 원칙 (CLAUDE.md 재확인)

- `twinspace_platform/` 하위 전부 = **업무(TwinSpace)**. 외부 공개 학습 산출물에 원본 소스를 그대로
  넣는 것은 CLAUDE.md 원칙("업무 프로젝트는 TwinSpace뿐", 업무 레포 취급 규정)에 위배될 소지.
- **단, 중요한 발견**: `sysadmin-front/`(=구 egovGeoportal)의 `LICENSE` 파일을 실측 확인한 결과
  **Apache License 2.0**이 박혀 있다. `ai_model` 저장소 자체(`genishs/llmmodelforreact`)도
  GitHub상 **Public, Apache-2.0**으로 확인됐다(`gh repo view`).
  - 이게 "TwinSpace가 의도적으로 이 코드를 공개 라이선스로 배포하겠다"는 뜻인지, 아니면 스캐폴딩에
    쓴 `egovframe-template-simple-react`(공개 eGovFrame 표준 템플릿)에서 **상속된 보일러플레이트
    잔재**일 뿐인지는 **이 조사만으로 판정 불가**. eGovFrame 자체가 대한민국 행정안전부가 배포하는
    공개 프레임워크(표준 템플릿은 통상 Apache-2.0)라, sysadmin-front의 상당 부분(공통컴포넌트
    `EgovSelect`/`EgovPaging`류, 샘플 페이지 `EgovCondition`/`EgovInfoPopup`류)이 실제로는
    "TwinSpace 고유 업무로직"이 아니라 "공개 템플릿을 그대로 쓴 부분"일 가능성이 있다.
  - **교차확인**: `study/egovframe-template-simple-react`(순수 공개 eGovFrame 템플릿, 정부 표준
    스캐폴딩) 역시 **동일한 Apache License 2.0** LICENSE 파일을 갖고 있다. sysadmin-front가 바로 이
    템플릿에서 스캐폴딩됐다는 정황(메모리 인덱스에 두 트리를 "다른 템플릿"으로 명시 구분한 기록 존재)과
    맞물려, sysadmin-front의 LICENSE는 **TwinSpace가 의도적으로 부여한 게 아니라 템플릿에서 그대로
    상속된 보일러플레이트일 가능성이 높다.**
  - **권고**: 이 판정을 앜선생이 임의로 내리지 않는다. 두목 또는 TwinSpace 계약 담당에게
    "sysadmin-front가 실제로 공개 라이선스 배포 대상인지"를 확인받기 전까지는, **기존 CLAUDE.md
    원칙(업무 소스는 외부 비공개 취급)을 그대로 따르는 게 안전**하다. 현재 `data/handcrafted_synth_egovreal.jsonl`과
    `eval_results/gen/*.tsx`(모델이 생성한 파생 코드, 원본 아님)는 이미 public 저장소에 커밋되어 있음 —
    문제가 있다면 이번 기회에 같이 재검토 필요(단, 이건 이번 임무 범위 밖이라 언급만 하고 별도 이슈로 분리 권고).

---

## 5. 권고안

### 5-A. 핵심 권고 — "대량 확보"는 하지 않는다

§2에서 확인했듯 이 파이프라인은 **데이터 양 증가에 반복적으로 회귀로 반응**했다(4060/8060 교차 재현).
범용 React 코퍼스(the-stack 등)를 대량으로 섞어 넣는 것은 **직접적인 반증 사례(분포 희석)와 같은
실패 패턴을 반복할 위험이 매우 높다.** 지금 우선순위로 두지 않는다.

### 5-B. 유효하다고 판단하는 확장 (하되, 소량·표적)

1. **GH API 수집의 "채택률" 개선** (§3-A) — 레포를 더 추가하기보다, `collect_github_data.py`가
   함수/컴포넌트 단위로 더 잘게 잘라 cap(384토큰) 안에 드는 조각을 더 많이 뽑도록 개선. 비용: 낮음
   (스크립트 수정, 신규 다운로드 없음). 겸사겸사 `jotaijs/jotai` 경로 버그(§3-A 부수 발견)도 고칠 것.
1'. **`ugfacility_pr/src`(사내, 32개 전부 .tsx/.ts, 7,950줄) 검토** — §4-A에서 확인했듯 이게 이
   장비에서 유일하게 볼륨 있는 "우리 팀이 직접 짠 TS 네이티브" 자산이다. sysadmin-front는 100% 레거시
   JSX라 "정답 TSX가 실제로 어떻게 생겼는지"를 프로젝트 내부에서 배울 데이터가 지금은 `handcrafted_synth_egovreal.jsonl`
   10건뿐인데, ugfacility_pr을 (오염가드 통과 전제로) 소량 편입하면 이 공백을 사내 실제 코드로 메울 수
   있다. 단 사내 산출물이므로 **공개 배포용 데이터셋에는 절대 넣지 말 것** — 내부 학습에만.
1''. **`egovframe-template-simple-react`(Apache-2.0, 이미 로컬에 있음, 77 jsx) 소량 편입** — 같은
   eGovFrame 관례 계열이면서 라이선스가 완전히 깨끗하고 eval과 겹치지 않는 별도 트리다.
2. **`error-taxonomy.md`가 지목한 스킬 전용 예제 계속 추가** — 지금 하던 방식(round4~7) 그대로 계속.
   외부 소스가 필요하다면 **the-stack-smol(2.6GB)에서 해당 스킬 패턴(제네릭 컴포넌트, discriminated
   union reducer 등)이 담긴 파일만 grep으로 골라내는 것** 정도가 실용적 상한선 — the-stack-v2 풀
   파이프라인 구축은 지금 얻을 이득 대비 과함.
3. **the-stack-v2 본격 도입은 보류.** 엔지니어링 비용(라이선스 재필터링 + 콘텐츠 2단계 다운로드)이
   불확실하고, 설령 받아도 §2-C에서 지적한 "JS→TS 변환 스킬을 가르치는 것"이라는 이 프로젝트의 본질과
   안 맞을 수 있다(the-stack은 완성된 TSX 코드이지 "JS→TS 변환 사례"가 아님 — 다른 태스크 형식이 필요).

### 5-C. 데이터 품질 관리 원칙 (확장하게 될 경우)

- **길이 상한 엄수**: round7/distill 트랙에서 실측된 대로, cap(384~1024 토큰) 초과 예제는 학습에
  넣지 말 것 — 잘림이 오답으로 학습된다.
- **instruction dedup 유지**: 현재 로더가 instruction 중복을 자동 제거하는 구조를 그대로 유지.
- **클래스형 컴포넌트 배제**: 외부 소스(the-stack, 오래된 GH 레포)에는 React 16 이전 class
  component가 섞여 있을 수 있음 — `class .* extends React.Component` 패턴 필터링 필요(현재
  `quality_filter()`에는 이 필터가 없음 — 확장 시 추가 권고).
- **eval 오염 가드 유지**: 외부 소스를 추가해도 `guard_eval_leak.py`의 3중 검사(파일명/식별자/콘텐츠
  해시)를 반드시 통과시킬 것 — 특히 우연히 heldout 파일과 유사한 패턴(EgovSelect류 이름)이 공개
  코퍼스에 섞여 들어올 가능성은 낮지만 구조적으로 열어두면 안 됨.
- **라이선스 태깅**: 지금은 `data/raw/github_react_qa.jsonl`에 출처 레포 정보가 없다(§2-B, 필드가
  instruction/input/output뿐). 외부 소스를 확장하려면 **각 샘플에 origin_repo/license 필드를 추가**해
  나중에 귀속 의무를 추적할 수 있게 해야 한다 — 지금 방식대로 늘리면 나중에 "이 예제가 어디서 왔는지"
  못 밝히는 사고가 난다.

### 5-D. 우선순위 — 지금이 아니라 나중

CLAUDE.md와 `docs/progress-20260802.md`가 이미 명시하듯, 현재 프로젝트의 실제 병목은:
1. **평가/채점 인프라** — 배치디코드 미검증(이슈 #9), 대형모델(72B~141B) heldout 채점이 시간 초과로
   부분측정에 그침, llama.cpp 경로 이제 막 구축.
2. **측정 신뢰성** — v1 채점기의 seed 분산 ±20pp·백틱 아티팩트가 드러나 v2로 막 재건한 참.

이 두 가지가 해결되기 전에는 **데이터를 더 넣어도 "그게 정말 좋아졌는지" 판별할 방법이 불안정하다.**
데이터 확보(특히 대량 외부 코퍼스)는 **후순위**로 두고, 하더라도 §5-B의 소규모·표적 확장에 그치는 것을
권고한다. 예상 비용: 5-B-1(스크립트 개선) 반나절, 5-B-2(스킬 표적 소량 추가) 지금 하던 라운드 케이던스
그대로(라운드당 반나절~하루), 5-B-3(the-stack-v2)은 **착수 자체를 보류**.

---

## 부록 — 참고한 실측 근거 파일

- `src/build_dataset_v2.py`, `src/build_dataset.py`, `src/collect_github_data.py`
- `scripts/eval_hard_tsc.py`, `scripts/score_v2.py`, `comms/v2-proposal/guard_eval_leak.py`, `comms/v2-proposal/tasksets_v2.json`
- `comms/error-taxonomy.md`, `comms/from-4060.md`, `comms/from-8060.md`, `comms/distill/README.md`
- `docs/model-training-history.md`, `docs/progress-20260802.md`
- `data/round4_manifest.md`, `data/round5_manifest.md`, `data/round7_manifest.md`, `data/handcrafted_synth_admin_round6_manifest.md`
- `comms/scores-4060-v2.jsonl`(base-vs-LoRA 대조군 실측값), `eval_results/7b-BASE-noLoRA-q8-mn4096.json`
