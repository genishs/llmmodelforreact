# round4 학습데이터 매니페스트 (handcrafted_round4.jsonl)

라운드4 약점 정조준 데이터. tsc 하드평가에서 드러난 4060의 2가지 약점을 겨냥한다.

- 총 19쌍 / 지시문 19개 전부 유일(합성 로더 instruction dedup 호환).
- **A. 제네릭 컴포넌트 11쌍**(약점1: `<T extends ...>` 제약, `keyof T`, `T[keyof T]`/`T[K]` 인덱싱,
  render prop, `JSX.Element`/`React.ReactNode` 반환타입, .tsx 화살표 제네릭 모호성 `<T,>` 회피,
  제네릭 객체 스프레드 캐스트). DataTable/List/GenericSelect/DetailView/Field/Autocomplete/
  GenericForm/TreeView + 제네릭 훅 useSelection/useSortable/usePagination.
- **B. import 보존 변환 8쌍**(약점2: JS→TS 변환 시 원본의 모든 import(컴포넌트/훅/유틸/이미지/CSS)를
  하나도 빠뜨리지 않고 보존 + props interface + 타입주석). BoardItem/SearchField/ProfileCard/
  SideMenu/AttachmentButton/ConfirmModal/TabBar/CommentForm.

## 위생 수칙 (필수 준수)
- eval 하드평가 대상 파일(`components/EgovPaging.jsx`, `pages/support/download/EgovDownloadDetail.jsx`)의
  내용/변환은 학습쌍에 **포함하지 않음**(오염 금지). `EgovLeftNav` 같은 eval-누수 식별자도 미사용.
- 모든 예제는 IP-clean하게 직접 작성(외부 회사 소스 미사용).
- 19/19 output 전부 strict TypeScript(`strict:true, noImplicitAny:true`)로 `tsc --noEmit` 클린 컴파일 검증 완료.
