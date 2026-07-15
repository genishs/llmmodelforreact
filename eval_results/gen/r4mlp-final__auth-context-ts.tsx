import React, { createContext, useContext, useState } from 'react';

interface User { id: string; name: string; email: string; }
interface AuthContextValue { user: User | null; login: (u: User) => void; logout: () => void; }

const AuthCtx = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  return <AuthCtx.Provider value={{ user, login: setUser, logout: () => setUser(null) }}>{children}</AuthCtx.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthCtx);
  if (!ctx) throw new Error('AuthProvider 밖에서 useAuth를 쓴 거야?');
  return ctx;
}