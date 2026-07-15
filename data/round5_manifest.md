# round5 학습데이터 매니페스트 (handcrafted_synth_round5.jsonl)

라운드5. held-out가 입증한 최강 레버(=import 보존 + 다양한 실파일형 JS→TS 변환)를 양·다양성으로 키운다.
빌더 글롭 `data/handcrafted_synth*.jsonl`에 자동 포함됨. 전 예제 IP-clean 직접 작성(외부 회사 소스 미사용).

- 총 34쌍 / 지시문 34개 전부 유일(파일명 포함). 합성 로더 instruction dedup 호환(다른 synth 파일과 충돌 0).

## A. import 보존 JS→TS 변환 — 24쌍 (주력)
각 input은 4~8종의 다양한 import(자식 컴포넌트/커스텀 훅/유틸/상수/CSS/이미지·SVG asset/라우터/아이콘/
ReactDOM portal/redux 등)를 갖고, output은 **모든 import를 한 줄도 빠짐없이 보존** + props interface +
상태/이벤트핸들러/함수 타입 명시 + 사용한 모든 이름이 import됨(미정의 0). 컴포넌트 종류·크기 다양:
- 리스트/테이블: NoticeList
- 카드: ProductCard / 상세뷰: ArticleDetail(`location.state as ...` 캐스트, useParams as 캐스트)
- 검색바: SearchBar / 폼: LoginForm / 페이지네이션: Pager / 필터: FilterPanel
- 모달(portal): ConfirmDialog / 팝업(toast): ToastPopup / 탭: TabPanel / 네비: TopNav
- 파일첨부: FileUploader(useRef<HTMLInputElement>, files?.[0]) / 갤러리: PhotoGallery
- 아코디언: FaqAccordion / 댓글(리스트+폼): CommentSection / 사이드바 트리: SidebarMenu(재귀 렌더)
- 빵부스러기: Breadcrumb / 별점: RatingStars / 그리드 툴바: DataGridToolbar(SVG ReactComponent import)
- 알림 드롭다운: NotificationBell / 스텝위저드: StepWizard(ComponentType) / 장바구니: CartSummary(useMemo)
- 대형 2개(import 多·JSX 깊음): DashboardPage, ProfileEditPage(제네릭 setField<K extends keyof Profile>)

## B. 약점 패턴 — 10쌍
held-out/11태스크 잔여 실패 정조준(다양한 변형):
- 제네릭 컴포넌트 React key: `key={String(item[idField])}` (keyof T는 symbol 포함 가능→String 래핑). GenericList, ChipSelect.
- React.FC + children(React18은 children 미포함): Card(React.FC + `children: React.ReactNode` 명시), PageLayout(일반 함수형 + ReactNode 슬롯).
- 판별 유니온 reducer: useTodos(ADD/TOGGLE/REMOVE/CLEAR_COMPLETED), cartReducer(ADD_ITEM/REMOVE_ITEM/UPDATE_QTY/CLEAR).
- 제네릭 훅 union 상태: useFetch<T>(idle/loading/success/error), useAsync<T>(idle/pending/resolved/rejected).
- 타입 안전 훅: useToggle(튜플 반환), usePrevious<T>(T|undefined).
- 함수 인자 개수 정확(TS2554 대비): useReorder(`move(from:number,to:number)` 고정 시그니처, 호출 시 인자 2개 정확).

## 위생 수칙 (필수 준수, 검증 완료)
- 다음 eval/held-out 대상 식별자를 학습쌍에 **0건** 포함(내용/변환/파일명): `EgovPaging`, `EgovDownloadDetail`,
  `EgovSelect`, `EgovImageGallery`, `EgovAboutOrganization`, `EgovAttachFile`, `EgovInfoPopup`, `EgovCondition`.
  grep 결과 8개 식별자 0건, `Egov` 문자열 자체도 0건.
- 실제 egov 파일을 읽지 않고 전부 합성으로 작성(IP-clean).
- 34/34 output 전부 strict TypeScript(`strict:true, noImplicitAny:true`, jsx:react)로 `tsc --noEmit` 클린 컴파일 검증 완료
  (미정의 import는 `declare module "*"` 와일드카드로 any 처리하여 우리가 붙인 타입만 엄격 검증).
- 빌드 반영: `build_dataset_v2.py --cap 1024 --gh-out-cap 512` 재빌드 시 34쌍 전부 토큰 한도 내(최대 1017토큰) 채택.
