import React from 'react';
import Avatar from './Avatar';
import Bio from './Bio';
import { useProfile } from '../hooks/useProfile';

interface ProfileCardProps {
  userId: number;
}

function ProfileCard({ userId }: ProfileCardProps) {
  const profile = useProfile(userId);
  return (
    <section>
      <Avatar src={profile.avatarUrl} alt={profile.name} />
      <h2>{profile.name}</h2>
      <Bio text={profile.bio} />
    </section>
  );
}

export default ProfileCard;