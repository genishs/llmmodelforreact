# v2 태스크셋 확장 제안 (양노드 합의 대상, 정본 아님)

앗선생(system-architect) 설계, 2026-07-17. **`scripts/` 정본 교체 전 halo 합의용.**

## 파일
- `tasksets_v2.json` — heldout7(앵커)/core16/canary4/xl3 태스크셋 정의 + core20 union 뷰. 언어중립 JSON.
- `guard_eval_leak.py` — 학습 오염 차단 3중 가드(파일명+식별자+**content-hash SHA256**). `data/*.jsonl` 전체 union 스캔.

## 핵심
- **Core-16**: clean 53풀에서 도메인 9층화(admin 2로 억제)·크기분포(2-5KB 4/5-10KB 10/10-20KB 2). 전부 3중검증 CLEAN.
- **★리네임 위장 오염 실증**: EgovAdminAppStatList가 `handcrafted_admin_round6.jsonl` rec1과 content-hash 완전일치. 파일명·식별자 grep은 통과, 해시만 포획. (실피해 없음 — synth글롭 미포함으로 학습 미투입. 단 가드 없으면 미래 위험.)
- **등가화**: heldout7 앵커는 byte-동일 유지, 별도유지+통계브리징(병합 시 평균이동 재발).

## 채택 절차
1. halo가 8060서 Core-16 파일존재+오염 독립확인
2. 양노드 `guard_eval_leak` 빌더에 채택(다음 데이터빌드 전 필수)
3. seed스윕과 **함께** 실제 20태스크 생성/채점(단독배포 금지 — seed 노이즈 미측정)

## 한계 (정직)
Core-16·heldout7 모두 egov 스캐폴딩 **템플릿 내 일반화** 측정. 진짜 OOD는 egov 밖 리액트 코퍼스 필요(별건).
