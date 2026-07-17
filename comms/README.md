# 8060 ↔ 4060 통신 프로토콜 v1 (합의 2026-06-26)

두 노드가 **독립적으로 동일 설계를 제안**해 합의됨(8060=maildir 제안 A, 4060=results.jsonl 제안).
충돌 없는 팀별 파일 방식(8060 안)을 채택.

## 채널 구성 (maildir = 팀별 분리 파일, 동시 push 충돌 0)
- **`comms/from-4060.md`** / **`comms/from-8060.md`** — 각 팀은 **자기 파일에만 append**.
  사람용 메시지(토론·제안·해석). 서로 다른 파일이라 동시 push해도 충돌 없음.
- **`comms/scores-4060.jsonl`** / **`comms/scores-8060.jsonl`** — eval 결과 **1줄=1측정 JSON**.
  기계가독·diff 쉬움·충돌 없음. 산문 표 대신 이걸 정본으로.
- **`docs/competition-log.md`** — 사람용 내러티브 인덱스(가끔 요약만). 신규 메시지는 여기 말고 위로.

## 커밋 메시지 규약 (4060 추가 제안)
- 발신 방향 접두: `[4060→8060]` / `[8060→4060]`. watcher가 발신자 확실히 구분.

## scores jsonl 스키마 (한 줄)
```json
{"round":3,"node":"4060","adapter":"rank16","base":"4bit","harness":"eval_hard_tsc",
 "harness_ver":"11task-mn2048-lf","max_new":2048,"pct":87.3,"clean":8,"max":11,"errors":7,
 "per_task":{"counter-ts":1.0,"egov-download-ts":0.6},"ts":"2026-06-26"}
```
- `harness_ver`로 같은 태스크셋·옵션인지 즉시 대조. `base`로 4bit/fp16 교차측정 구분.
- `node`=어댑터 소속 노드, 측정 수행 노드는 파일명(scores-4060=4060이 측정). 교차측정은 `"measured_by":"4060"` 추가.

## 규칙
- append-only. 기존 줄 수정·삭제 금지(정정은 새 줄 + from-*.md에 사유).

## ⚠ 정본 egov 소스 트리 (2026-07-17 추가 — 잘못된 트리 사고 재발 방지)
8060 박스에는 egov 소스 트리가 **≥3개** 존재하는데(다른 템플릿, node_modules 사본 포함),
`scripts/eval_hard_tsc.py:_resolve_egov()` 가 실제로 채점에 쓰는 건 **딱 하나**뿐이다.
잘못된 트리로 채점하면 apples-to-oranges 오탐이 난다(실제로 겪은 사고).

- **정본**: `<workspace>/twinspace_platform/egovGeoportal/src` (84 jsx, heldout7 앵커 전부 존재)
- **아님**: `<workspace>/study/egovframe-template-simple-react/src` (다른 템플릿, 77 jsx — eval 미사용)
- 두 노드 모두 `EGOV_SRC` 환경변수를 **명시적으로 export** 하는 걸 강력 권장:
  ```bash
  export EGOV_SRC="/run/media/user/새 볼륨/Documents/workspace/twinspace_platform/egovGeoportal/src"   # Linux/8060
  set EGOV_SRC=d:/Documents/workspace/TwinSpace-platform/egovGeoportal/src                              # Windows/4060
  ```
- `_resolve_egov()`는 이제 (1) 어느 트리로 잡혔는지 항상 print하고, (2) heldout7 앵커 7개 중
  하나라도 없으면 **즉시 FileNotFoundError로 중단**한다(잘못된/불완전한 트리로 조용히 채점하는 것 방지).
