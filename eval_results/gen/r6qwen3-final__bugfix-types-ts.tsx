import React, { useState } from 'react';
type Props = { user: { id: number; name: string; age: number }; };

function UserCard({ user }: Props) {
  const [count, setCount] = useState(0); // 문자열 → 숫자로 변경
  const handleClick = () => setCount((c) => c + 1); // 함수형 업데이트
  const isAdult = user.age >= 18; // boolean이 아닌 string으로 사용하지 않도록
  const label = count.toString(); // 레이블을 숫자 카운트로 표시
  return (
    <div style={{ cursor: 'pointer' }} onClick={handleClick}>
      {user.name} ({count})
      {isAdult ? <span style={{ color: '#2ecc71', marginLeft: 4 }}>Adult</span> : null}
    </div>
  );
}

export default UserCard;