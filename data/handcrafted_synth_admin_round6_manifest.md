# handcrafted_synth_admin_round6 매니페스트

round6b SOLO: full-page admin 변환이 seq768을 넘어 잘림 → 짧은 admin 패턴 스킬 10개로 피벗.
각 스킬 ≤768 full-prompt 토큰 + tsc 단독컴파일 0에러(strict, TS2347 제외) 검증.

- 합격 10/10 (instruction 전부 유일).

## admin-list-table  [pass]  tokens=285
- instruction: 관리자 게시판 목록 테이블 컴포넌트를 TypeScript로 작성해줘. rows를 BoardRow[]로 받고, 각 행에 수정/삭제 버튼을 두되 onClick 핸들러가 id: number를 받도록 타입을 붙여줘(BoardTable). 코드만 출력.

## admin-list-paging  [pass]  tokens=268
- instruction: 관리자 목록 페이지네이션 상태를 TypeScript로 작성해줘. page/totalPage를 가진 PagingState를 useState로 관리하고 페이지 변경 핸들러에 next: number 타입과 범위 가드를 붙여줘(AdminListPaging). 코드만 출력.

## admin-search-form  [pass]  tokens=281
- instruction: 관리자 검색/필터 폼을 TypeScript로 작성해줘. searchCnd/searchWrd를 가진 SearchCondition 상태 객체와, select·input 공용 onChange를 React.ChangeEvent<HTMLSelectElement | HTMLInputElement>로 타입지정해줘(AdminSearchForm). 코드만 출력.

## admin-location-state  [pass]  tokens=247
- instruction: 관리자 수정 페이지에서 react-router의 useLocation().state를 안전하게 타입지정하는 예제를 TypeScript로 작성해줘. NoticeEditState 인터페이스를 정의하고 state를 'NoticeEditState | null'로 단언한 뒤 옵셔널 체이닝으로 읽어줘(NoticeEditPage). 코드만 출력.

## admin-edit-submit  [pass]  tokens=308
- instruction: 관리자 수정 폼 제출 핸들러를 TypeScript로 작성해줘. React.FormEvent<HTMLFormElement>로 onSubmit을 타입지정하고, 제어 input들을 ManagerForm 상태로 묶고, 제출 시 필수값 가드를 넣어줘(ManagerEditForm). 코드만 출력.

## admin-detail-nullguard  [pass]  tokens=223
- instruction: 관리자 상세보기 컴포넌트를 TypeScript로 작성해줘. detail을 'NoticeDetail | null' props로 받아 null 가드(early return)로 TS18047을 피하고, 값이 있을 때만 필드를 렌더링해줘(NoticeDetailView). 코드만 출력.

## admin-jsx-attrs  [pass]  tokens=238
- instruction: JSX 숫자/불리언 속성 타입을 올바르게 쓴 관리자 폼 필드 컴포넌트를 TypeScript로 작성해줘. colSpan={n}, tabIndex={0}, cols={30}/rows={10}, readOnly를 문자열이 아닌 올바른 타입으로 지정해줘(AdminFormFields). 코드만 출력.

## admin-groupend  [pass]  tokens=191
- instruction: 관리자 핸들러에서 console.group/groupEnd를 올바르게 쓴 예제를 TypeScript로 작성해줘. console.groupEnd()는 인자 없이 호출(TS2554 회피)하고 useCallback 핸들러에 반환타입 void를 붙여줘(AdminLogPanel). 코드만 출력.

## admin-status-badge  [pass]  tokens=227
- instruction: 상태 배지를 렌더 콜백으로 그리는 관리자 테이블을 TypeScript로 작성해줘. rows: AdminRow[]와 renderBadge 콜백(status를 받아 React.ReactNode 반환)을 props 인터페이스로 타입지정해줘(StatusBadgeTable). 코드만 출력.

## admin-useeffect-fetch  [pass]  tokens=242
- instruction: 관리자 목록을 useState 배열 + useEffect fetch로 불러오는 컴포넌트를 TypeScript로 작성해줘. NoticeItem[] 상태와 NoticeResponse 응답 형태를 정의하고 fetch().then 체인에 타입을 붙여줘(AdminNoticeList). 코드만 출력.
