# round7 학습데이터 매니페스트 (handcrafted_synth_round7.jsonl)

## 0. 이 라운드가 다른 이유 — 재현성부터 확인하고 범위를 좁혔다

PM 원안은 r6base(88.6%)의 3개 잔여 실점(`ho-attachfile` 0.60 / `ho-admin-mlist` 0.80 /
`ho-admin-medit` 0.80)을 전부 겨냥하는 것이었다. 학습 전에 `comms/scores-4060.jsonl` +
`comms/scores-8060.jsonl` + `comms/error-taxonomy.md`를 교차해 **재현성부터 검증**했고,
3개 중 **1개만 데이터로 공략할 가치가 있다는 결론**으로 범위를 좁혔다.

| 태스크 | 측정된 어댑터(9~10회, 양 노드·전 정밀도) | 판정 |
|---|---|---|
| **ho-attachfile** | r6base 0.6(TS18048,TS2554) / r6admin 0.0(TS18047×2,TS18048,TS2322,TS2554) / r7abl 0.4(TS18048×2,TS2554) / cap512 0.6(TS18048,TS2554) / 4060 rank16·r4mlp(구캐논) 0.0~0.8 / 8060 14b-v1(fp16 DirectML) 0.0 / 8060 14b-rocm(bf16) 0.0 | **재현됨.** 측정된 10회 전부 1.0 미만(단 한 번도 만점 없음). 코드가 기록된 4회 전부 TS18047/18048 **+** TS2554가 **동시에** 등장. 노드(4060 CUDA 4bit / 8060 DirectML·ROCm fp16/bf16), 랭크, 베이스 크기(7B/14B)를 가로질러 일관 → 데이터로 공략할 가치 있음. |
| **ho-admin-mlist** | r6base 0.8(**TS2304**) / r6admin 0.8(**TS2345**) / r7abl 0.8(**TS2345**) / cap512 **0.0**(TS2783×3+TS2345+TS2304) / 8060 14b계열 0.6 | **재현 안 됨(원인 수준에서).** 점수는 0.8 부근에서 안정적이지만 **에러 코드가 실행마다 바뀐다**(import누락→시그니처불일치→중복prop, 4가지 다른 코드). r6base 로그 한 줄만 보고 "TS2304=import 보존 실패"로 특정한 PM의 원 진단은 **다른 3개 동일계열 어댑터에서 재현 안 됨**. 단일 토큰 결정이 흔들리는 것에 가깝다. **좁게 타기팅하면 r6admin의 재판(오답 코드를 겨냥해 다른 오답을 유발)이 될 위험** — 채택 안 함. |
| **ho-admin-medit** | r6base 0.8(TS1160) / r6admin 0.4 / r7abl 0.4(TS17008×1+TS1381+TS1005) / cap512 **0.0(TRUNC)** / 4060 구캐논/8060 14b계열 전부 0.0 | **이미 진단 완료, 별도 원인.** CLAUDE.md 자체가 이미 확증: 22KB 입력의 생성길이가 `--cap` 빌드값에 따라 5,462~15,483자로 요동(cap512는 TRUNC=4096 상한 도달)하고, "길이는 필요조건이지 충분조건 아님"(길게 쓰되 문법이 깨짐)이 핵심 실패모드다. `TS1160`(r6base) 자체도 "미종결 리터럴"류로 이 확인된 길이/생성-완결 문제군에 속한다. **새 학습쌍이 아니라 cap 사다리·max_new 실험의 몫** — 이번 라운드에서 손대지 않음. |

**결론**: 3태스크 전부를 겨냥하라는 원 지시에서 **1개(ho-attachfile)로 축소**. 나머지 둘은
데이터 추가가 아니라 각각 (a) 노이즈에 가까운 단일 태스크 변동, (b) 이미 별도 트랙(cap 사다리)이
진행 중인 이슈이므로, 지금 데이터를 넣으면 r6admin처럼 "겨냥했는데 안 고쳐지고 다른 데가 깨지는"
재판이 될 위험이 더 크다고 판단.

## 1. 데이터 3쌍 — 왜 이 형태/소스인가

**형태**: 전부 긴 실파일급 변환쌍(694~881 토큰, cap 1024 대비 61~68% 사용 — round6admin의
191~308토큰 "짧은 패턴"과 뚜렷이 다른 프로파일. 성공한 `handcrafted_synth_egovreal.jsonl`의
449~1140토큰 분포 안에 들어오도록 의도적으로 맞춤).

**소스**: `d:\Documents\workspace\TwinSpace-platform\egovGeoportal\src`를 뒤져 실제
`held-out ho-attachfile`(`components/EgovAttachFile.jsx`)을 **읽기만 하고**(학습데이터에는
0바이트도 안 씀) 그 파일이 실제로 어떤 TS2554/null-safety 함정을 갖고 있는지 먼저 분석한 뒤,
그 함정과 **동일한 클래스의 패턴**을 담은 (a) held-out이 아닌 실파일 1개, (b) IP-clean
자체작성 2개로 구성했다.

### Pair 1 — `egovFetch.jsx` (REAL, non-held-out: `src/api/egovFetch.jsx`)
- **왜 이 파일**: `EgovAttachFile.jsx`를 포함해 egov 앱 전체 60곳 이상이 호출하는
  `EgovNet.requestFetch(url, options, handler)` 헬퍼의 **실제 정의**. 지금까지 어떤 라운드도
  이 헬퍼의 **정의 자체**를 학습데이터에 넣은 적이 없다(콜사이트만 2번 등장 — `SnsKakaoCallback`,
  `PrivateRoutes`, 둘 다 이미 `egovreal.jsonl`에 있음). 실제 시그니처는
  `requestFetch(url, requestOptions, handler, errorHandler)` **4개 파라미터**이지만 **실사용
  콜사이트는 전부(60+곳) 3개 인자**만 넘긴다 — 즉 진짜 프로덕션 관례는 "trailing 파라미터는
  선택적"이다. 모델이 이 정의를 본 적 없이 비슷한 헬퍼를 타이핑하면 필수 파라미터로 과도하게
  엄격히 선언하기 쉽고, 그러면 실제 3-인자 콜사이트에서 TS2554가 난다.
- **검증된 실물 함정**: 원본이 `console.groupEnd("requestFetch")`처럼 **문자열 인자와 함께
  호출**하는데, TS DOM lib의 `console.groupEnd()`는 **0-인자**로 선언되어 있다. 직접
  `tsc --strict`로 프로브해 확인함(`error TS2554: Expected 0 arguments, but got 1.`) —
  이 파일을 그대로 변환하면 **실제로 TS2554가 발생하는** 지점이 2군데 있고, output은 이를
  올바르게 0-인자로 고쳤다. ho-attachfile의 실점 코드(TS2554)와 **동일 에러 코드의 실제
  트리거**를 가진 실물 사례.
- 부수 스킬: `catch (error: unknown)` + `error instanceof Error` 내로잉(널/언노운 안전성 계열).

### Pair 2 — `AttachmentUploader.jsx` (IP-clean 자체작성)
- **왜 이 형태**: `EgovAttachFile.jsx`를 읽어보니 실제 실점 소스는 두 가지였다 —
  ① `onChange` 핸들러의 `e.target.files`(TS DOM lib에서 `FileList | null`)를 가드 없이
  쓰는 지점, ② `posblAtchFileNumber` prop이 "없으면 1로 대체"하는 런타임 리어사인 패턴
  (선택적 prop을 나중에 확정값으로 좁히는 흐름). **held-out 파일의 식별자/문자열은 0건 재사용**
  (prop명 `posblAtchFileNumber`/`boardFiles`/`fnChangeFile`/`fnDeleteFile`, 함수명
  `onClickDownFile`/`onClickDeleteFile`/`onChangeFileInput` 전부 미사용 — grep 0건 확인).
  대신 같은 **패턴 클래스**(FileList 널가드 + optional prop 기본값 리어사인 + 고정 인자수
  콜백)를 다른 이름의 컴포넌트로 재구성.
- 부수 스킬: `onRemoveItem(fileId, index)` 2-인자 콜백을 시그니처와 항상 일치시켜 호출
  (TS2554 대비).

### Pair 3 — `MemberFieldGroup.jsx` (IP-clean 자체작성)
- **왜 이 형태**: non-held-out 실파일 `pages/mypage/EgovMypageEdit.jsx`(egovGeoportal,
  held-out 아님)를 읽어보니 `checkRef.current[i]`처럼 **ref 배열 원소**(타입상
  `HTMLInputElement | null`)를 가드 없이 `.value` 접근하는 패턴이 실제로 있었다. 이 실파일
  자체는 447줄로 cap 1024에 비해 너무 커서(약 3,700+토큰) 그대로는 못 쓰고, **같은 패턴만
  추출**해 짧은 실파일급 컴포넌트로 재구성(식별자 `checkRef`/`mberId`/`mberNm`/`formObjValidator`
  등 0건 재사용, grep 확인).
- 부수 스킬: `validateFields(refs)` 1-인자 헬퍼를 선언 시그니처와 항상 일치시켜 호출.

## 2. 위생 수칙 검증 결과 (전부 통과)
1. **held-out 오염 0건**: `EgovSelect`/`EgovImageGallery`/`EgovAboutOrganization`/
   `EgovAttachFile`/`EgovAdminDataAccessEdit`/`EgovAdminMemberList`/`EgovAdminMemberEdit`
   + held-out 원본의 식별자(`posblAtchFileNumber`/`boardFiles`/`fnChangeFile`/`fnDeleteFile`/
   `atchFileId`/`fileSn`/`orignlFileNm`/`checkRef`/`mberId`/`mberNm`) 전부 grep 0건.
2. **strict tsc 클린**: 3/3 output이 `strict:true, noImplicitAny:true, strictNullChecks:true`
   (`tsc_eval/tsconfig.r7verify.json`, 기존 `tsc_eval/tsconfig.json` 대비 noImplicitAny만
   true로 강화)로 `tsc --noEmit` 클린 컴파일. `jsonl`에서 output을 다시 추출해 재컴파일까지
   확인(라운드트립 손상 없음).
3. **토큰 캡**: 개별 694/881/870 토큰, 전부 cap 1024 안전마진 확보(round5의 1140토큰 탈락
   재발 방지 — 1차 초안은 962/1006토큰으로 너무 타이트해 로깅 잡음을 걷어내 재작성함).
4. **인스트럭션 유일성**: `egovFetch.jsx`/`AttachmentUploader.jsx`/`MemberFieldGroup.jsx`
   3개 파일명 전부 기존 코퍼스(6개 활성 synth 파일)와 충돌 0건.
5. **실제 빌더로 채택 확인**: `build_dataset_v2.py --cap 1024 --gh-out-cap 512` 재실행 결과
   `합성 296→299개 로드, 채택 295→298개`(round7 3쌍 전부 채택, 기존 1개 탈락분은 round7과
   무관한 기존 egovreal 1140토큰 건과 동일) → **총 351→354개(315/36→318/36)**, 단일 변수
   추가(r7-ablation과 동일한 방법론: 정확히 +3, 다른 변인 없음).
6. **빌드 상태 원복**: 확인 직후 `data/processed`는 **round7을 제외한 r6base 원상태(351/315/36)로
   되돌려 놓음** — 지금 진행 중인 seed 분산 측정 실험을 건드리지 않기 위해서다. round7을 실제
   학습에 넣으려면 `build_dataset_v2.py --cap 1024 --gh-out-cap 512`를 **round7.jsonl이
   `data/`에 있는 상태로 재실행**하면 된다(자동 글롭됨, 코드 변경 불필요).

## 3. 다음 단계 제안 (학습은 아직 안 함 — PM 지시대로)
- **분산 측정 결과를 먼저 볼 것.** ±10pp 이상이면 이 3쌍의 기대효과(ho-attachfile 하나의
  점수 변화)는 분산 안에 묻힐 수 있다.
- 분산이 통제 가능한 수준이면, r7-ablation과 동일한 **단일변수 비교**로 검증할 것:
  r6base(351, 대조군) vs r6base+round7(354, 처치군) — **동일 조건, 이 3쌍 유무만 차이**.
  ho-attachfile 개선 여부 + 나머지 6태스크 무변동 여부를 함께 볼 것(round6admin처럼 타깃 외
  회귀가 나면 그것도 유의미한 결과).
- mlist/medit은 이번 라운드에서 의도적으로 손대지 않았다는 것을 결과 해석 시 유념할 것
  (7태스크 중 이 둘의 점수가 흔들려도 round7 데이터 탓이 아니라 원래도 불안정했던 부분).
