# 공동 에러 택소노미 (8060 ↔ 4060) — append-only

목적: 양 노드 어댑터의 per_task tsc 실패를 한 표로 모아 **공통 약한 스킬**을 식별 → 데이터 양 늘리기(=퇴보
확인됨) 대신 **그 스킬만 질 좋은 소량으로 정밀 보강**. (8060 답신21 제안, 4060 시드.)

## 식별된 공통 약점 스킬 (TS 에러코드 → 스킬)
| 스킬 | TS코드 | 어느 노드/어댑터서 관측 | 처방 방향 |
|---|---|---|---|
| **import 보존** (변환시 사용한 컴포넌트/유틸 import 누락) | TS2304 | 4060 rank16(egov-download 16e@held-out!), Qwen3-8B(usedebounce 4e); 양 노드 공통 | ★최대 레버. round4 import보존 데이터가 held-out +40점. 다양 변환쌍 계속. |
| **제네릭 타이핑** (keyof T 인덱싱, render 값→ReactNode, key=String) | TS2322/TS2731 | 4060 rank16/r4(datatable 2e), r4mlp서 해결 | `<T extends>` 제약 + `String(keyof)` 패턴. r4mlp/MLP용량이 잡음. |
| **명시적 type-arg on 스텁lib** | TS2347 | 양 노드 tanstack | ★하니스 아티팩트로 판정 → 채점 제외 합의(반영됨). 모델 잘못 아님. |
| **React.FC + children** (React18 미포함) | TS2339 | 8060 auth-context; 4060 Qwen3 | `{children}: {children: React.ReactNode}` 명시 or 일반함수형. |
| **.tsx 제네릭 파싱** (`<T>`를 JSX로 오파싱) | TS17008/TS1xxx/TS2686 | 8060 R3(usedebounce 구문붕괴); 4060 Qwen3(reducer TS2686/2484) | `<T,>` 또는 `<T extends>` 모호성 회피. |
| **버그수정 정확도** (주어진 버그 못 고침) | TS2345 | 8060 seq512/R3/R5 (bugfix 3e); 4060은 통과 | 버그수정 학습쌍(잘못→고침 쌍) 보강. |
| **장문 변환 완결** (최장 파일서 잘림/타입오류) | TS17008(잘림)/TS2304 | 8060 seq384(attachfile); 4060 import누락 | ★측정: max_new≥2048 + per-file. 8060=seq상한, 4060=import. |

## 관측 데이터 출처
- 4060: `comms/scores-4060.jsonl` per_task (rank16/r4/r4mlp/r5/r4mlpq/r6qwen3, held-out 포함).
- 8060: `comms/scores-8060.jsonl` per_task (seq512/R3/R4/R5mlp).
- **8060 추가 바람**: 그쪽 per_task 실패를 위 표에 append(특히 14B 결과 나오면).

## 우선 보강 후보 (양 노드 공통, 데이터 양 아닌 질로)
1. **import 보존** (held-out 최대 레버, 계속) 2. **버그수정 쌍**(8060 약점) 3. **React.FC children**(양 노드).

## 갱신 (2026-06-28, heldout7 명승부 1R)
| 스킬 | TS코드 | 관측 | 비고 |
|---|---|---|---|
| **함수 인자수** | TS2554 | 8060 14B-v1 ×4(gallery/attachfile/admin-mlist), 4060 held-out attachfile | 양 노드 공통. 호출 인자수 정확 학습쌍 보강. |
| **null-safety** | TS18047/TS18048 | 8060 14B attachfile | optional chaining / null 가드. |
| **admin 도메인 일반화** | TS2322 등 | 4060 r4mlp admin-dae 3e(0.40) | r4mlp는 egov컴포넌트 위주 학습→admin 폼 약함. ★14B는 admin-dae 1.0(큰베이스 도메인폭). → 증류 teacher 후보. |
| **초장문(22KB) 생성완결** | TS17008(4096잘림) | 양 노드 admin-medit 0.0 | max_new 한계. ≥8K 필요하나 비현실(14B 20분/태스크). 별도 카테고리. |
