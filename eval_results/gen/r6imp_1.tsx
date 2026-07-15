import React from 'react';
import UserRow from './UserRow';
import { useUsers } from '../hooks/useUsers';

interface UserListProps {
  teamId: number;
}

function UserList({ teamId }: UserListProps) {
  const { users, loading } = useUsers(teamId);
  if (loading) {
    return <p>로딩중...</p>;
  }
  return (
    <ul>
      {users.map((u: { id: number }) => (
        <UserRow key={u.id} user={u} />
      ))}
    </ul>
  );
}

export default UserList;