import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "../api/client";
import type { Me } from "../api/types";
import { UNAUTHORIZED_EVENT } from "../lib/auth";

interface AuthState {
  me: Me | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    api
      .me()
      .then((m) => alive && setMe(m))
      .catch(() => alive && setMe(null))
      .finally(() => alive && setLoading(false));
    // Any 401 later (session expired, signed out elsewhere) sends the person back to the login screen.
    const signedOut = () => setMe(null);
    window.addEventListener(UNAUTHORIZED_EVENT, signedOut);
    return () => {
      alive = false;
      window.removeEventListener(UNAUTHORIZED_EVENT, signedOut);
    };
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    setMe(await api.login(username, password));
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      setMe(null);
    }
  }, []);

  const value = useMemo(() => ({ me, loading, login, logout }), [me, loading, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const v = useContext(AuthContext);
  if (!v) throw new Error("useAuth must be used inside AuthProvider");
  return v;
}
