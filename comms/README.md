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
