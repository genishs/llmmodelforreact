// 미설치 모듈(react 제외)을 any로 폴백 → "Cannot find module"/false TS2305 노이즈 제거.
// 빈 형태 `declare module '*';` 는 named import도 any로 허용한다(export= 형태와 달리 false 페널티 없음).
// 실제 설치된 react/@types/react 는 해상도 우선순위가 높아 와일드카드와 무관하게 진짜로 타입체크된다.
// → tsc는 "모델이 작성한 TS 자체의 정합성"(JSX 유효성·interface/제네릭·타입주석·null안전)만 채점.
declare module '*';
