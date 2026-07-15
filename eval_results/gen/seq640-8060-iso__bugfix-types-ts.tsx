import React, { useState } from 'react';

interface User { id: number; name: string; age: number; }
interface UserCardProps { user: User; }

function UserCard({ user }: UserCardProps) {
  const [count, setCount] = useState<number>('0');
  const handleClick = () => setCount((prevCount) => (parseInt(prevCount) + 1).toString());
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