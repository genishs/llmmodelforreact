import React, { createContext, useContext, useState } from 'react';

interface User {
  id: string;
  name: string;
}

interface AuthContextValue {
  user: User | null;
  login: (u: User) => void;
  logout: () => void;
}

const AuthCtx = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  return (
    <AuthCtx.Provider value={{ user, login: setUser, logout: () => setUser(null) }}>
      {children}
    </AuthCtx.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthCtx);
  if (!ctx) throw new Error('AuthProvider 내부에서 사용하세요');
  return ctx;
}