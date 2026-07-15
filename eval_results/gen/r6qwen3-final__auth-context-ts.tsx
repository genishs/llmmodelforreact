import { createContext, useContext, useState } from 'react';

interface User {
  id: string;
  name: string;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(() => {
    try { return JSON.parse(localStorage.getItem('auth')!); }
    catch { return null; }
  });

  function login(u: User) { localStorage.setItem('auth', JSON.stringify(u)); setUser(u); }
  function logout() { localStorage.removeItem('auth'); setUser(null); }

  return <AuthContext.Provider value={{ user, login, logout }}>{children}</AuthContext.Provider>;
}

export default AuthProvider;

function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider');
  return ctx;
}