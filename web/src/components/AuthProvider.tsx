"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { clearToken, getToken, setToken } from "@/lib/auth";

type AuthState = {
  ready: boolean;
  username: string | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [username, setUsername] = useState<string | null>(null);
  const router = useRouter();

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const token = getToken();
      if (!token) {
        if (!cancelled) {
          setUsername(null);
          setReady(true);
        }
        return;
      }
      try {
        const me = await api.me(token);
        if (!cancelled) setUsername(me.username);
      } catch {
        clearToken();
        if (!cancelled) setUsername(null);
      } finally {
        if (!cancelled) setReady(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(
    async (user: string, password: string) => {
      const token = await api.login(user, password);
      setToken(token.access_token);
      const me = await api.me(token.access_token);
      setUsername(me.username);
      router.replace("/clients");
    },
    [router],
  );

  const logout = useCallback(() => {
    clearToken();
    setUsername(null);
    router.replace("/login");
  }, [router]);

  const value = useMemo(
    () => ({ ready, username, login, logout }),
    [ready, username, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

export function useRequireAuth() {
  const auth = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (auth.ready && !auth.username) {
      router.replace("/login");
    }
  }, [auth.ready, auth.username, router]);

  return auth;
}

export function explainError(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  if (err instanceof Error) return err.message;
  return "Something went wrong";
}
