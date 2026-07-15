import React, { useState } from 'react';

interface User { id: number; name: string; age: number; }

function UserCard({ user }: { user: User }) {
  const [count, setCount] = useState<number>(0);
  const handleClick = () => setCount((c) => c + 1);
  const isAdult: boolean = user.age >= 18;
  const label: string = user.name;
  return (
    <div onClick={handleClick}>
      {user.name} ({count}) {label}
      {isAdult && <span>Adult</span>}
    </div>
  );
}

export default UserCard;