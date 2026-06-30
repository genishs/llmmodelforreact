# 증류(distillation) 트랙 — 14B(8060) teacher → 7B(4060) admin 도메인 보강

## 목적
4060 r4mlp(7B)의 알려진 약점 = **admin 도메인 일반화**(held-out admin-dae에서 14B 1.0 vs r4mlp 0.40).
14B는 admin 도메인 폭이 넓으므로(답신23), 이를 **teacher로 써서 admin JS→TS 변환 타깃을 생성** →
4060이 tsc 통과분만 학습에 편입해 admin 약점을 정조준 보강한다.

## 데이터 위생 (★중요 — train=test 오염 금지)
held-out 평가셋의 admin 3파일은 **절대 증류/학습에 넣지 않는다**:
- `pages/admin/dataaccess/EgovAdminDataAccessEdit.jsx` (ho-admin-dae)
- `pages/admin/members/EgovAdminMemberList.jsx` (ho-admin-mlist)
- `pages/admin/members/EgovAdminMemberEdit.jsx` (ho-admin-medit)

`prompts.jsonl`은 이 3개를 제외한 **나머지 admin 19파일**만 타깃으로 한다(같은 eGovFrame admin 분포).

## 절차
1. **(4060, 완료)** `prompts.jsonl` 생성 — admin .jsx 변환 프롬프트 19개. 각 줄:
   `{id, domain, task, src_rel, sha256_lf, lines, instruction, note}`.
   - `src_rel` = `egovGeoportal/src` 기준 상대경로(양 노드 동일 프로젝트, LF sha256으로 동일입력 보장).
   - `sha256_lf` = 입력 .jsx를 **LF 정규화 후** sha256. 8060은 생성 전 자기 파일 해시가 일치하는지 확인.
2. **(8060, VRAM 재할당 후)** 각 `src_rel`을 읽어 14B로 strict `.tsx` 생성 → `comms/distill/gen-8060/<id>.tsx`로 저장.
   - 14B 추론 태스크당 ~20분이니 배치 5~10개씩, 급하지 않게. 초장문(>500줄)은 max_new 잘림 주의(나누거나 후순위).
3. **(4060)** `gen-8060/`의 각 .tsx를 **per-file tsc --noEmit**로 검증 → 통과분만 학습셋 편입 → r4mlp 재학습.
   - 검증 통과/실패를 `comms/distill/verify-4060.jsonl`에 기록(투명성).
4. **(4060)** 재학습 어댑터를 held-out7-mn4096 캐논으로 측정 → admin-dae/mlist/medit 개선 여부 확인.

## 현재 상태 (2026-06-30)
- prompts.jsonl 준비 완료(4060). 8060 장비가 다른 업무중이라 14B 생성은 **대기**.
- 그동안 4060은 **솔로 트랙** 병행: admin 일부 파일을 4060이 직접 strict-TS 변환·tsc검증해 선행 학습데이터로 제작
  (teacher 불필요). 8060 복귀 시 14B 생성분과 합쳐 비교/보강.

---

## ⚠️ 발견(2026-06-30 4060 솔로) — 풀페이지 admin 변환은 seq768 학습에 부적합
data-curator가 admin 6파일을 strict-TS로 변환·tsc 검증(6/6 pass, `verify-4060.jsonl`)했으나,
**full-prompt 토큰 측정 결과 2002/4189/4152/2661/1236/3219** — 4060 학습창 **seq768을 전부 초과**.
- 4060 학습셋 실측은 max 713 / p95 469(잘림 0)인데, 풀페이지 변환은 1.2K~4.2K → 768로 잘려 **학습에 해로움**.
- 결론: **풀페이지 변환(`data/handcrafted_admin_round6.jsonl`)은 학습 투입 금지**. 용도 = ①held-out류 평가/증류
  teacher(14B, seq제약 다름) 비교 참조 ②짧은 패턴 스킬 추출 소스.
- 솔로 학습 트랙 피벗: 위 변환을 소스로 **짧은(≤768) admin 패턴 스킬**(유일 instruction·tsc클린·IP-clean)을
  `data/handcrafted_synth_admin_round6.jsonl`(SYNTH_GLOB 매칭)로 제작 → build_dataset_v2(cap≥768) → r4mlp 재학습.
- 증류 트랙(8060 14B)은 seq제약이 우리와 달라 풀페이지 생성이 가능하니 그대로 유효(README 절차 변경 없음).
