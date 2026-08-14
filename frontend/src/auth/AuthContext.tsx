import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  ApiError,
  clearCsrfToken,
  getAuthSession,
  login as loginRequest,
  logout as logoutRequest,
  type AuthSession,
  type LocalRole,
  type LocalUser,
} from "../api/client";

type AuthStatus = "checking" | "authenticated" | "unauthenticated";

interface AuthContextValue {
  status: AuthStatus;
  user: LocalUser | null;
  expiresAt: string | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshSession: () => Promise<void>;
  hasRole: (...roles: LocalRole[]) => boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<AuthSession>({
    authenticated: false,
    user: null,
    expires_at: null,
  });
  const [status, setStatus] = useState<AuthStatus>("checking");

  const acceptSession = useCallback((next: AuthSession) => {
    if (next.authenticated && next.user?.active) {
      setSession(next);
      setStatus("authenticated");
    } else {
      clearCsrfToken();
      setSession({ authenticated: false, user: null, expires_at: null });
      setStatus("unauthenticated");
    }
  }, []);

  const refreshSession = useCallback(async () => {
    try {
      acceptSession(await getAuthSession());
    } catch (error) {
      if (!(error instanceof ApiError) || error.status !== 401) throw error;
      acceptSession({ authenticated: false, user: null, expires_at: null });
    }
  }, [acceptSession]);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    void getAuthSession(controller.signal)
      .then((next) => {
        if (active) acceptSession(next);
      })
      .catch((error: unknown) => {
        if (!active || (error instanceof DOMException && error.name === "AbortError")) return;
        acceptSession({ authenticated: false, user: null, expires_at: null });
      });
    const expired = () => acceptSession({ authenticated: false, user: null, expires_at: null });
    window.addEventListener("otsoc:session-expired", expired);
    return () => {
      active = false;
      controller.abort();
      window.removeEventListener("otsoc:session-expired", expired);
    };
  }, [acceptSession]);

  const login = useCallback(
    async (username: string, password: string) => {
      acceptSession(await loginRequest(username, password));
    },
    [acceptSession],
  );

  const logout = useCallback(async () => {
    try {
      await logoutRequest();
    } finally {
      acceptSession({ authenticated: false, user: null, expires_at: null });
    }
  }, [acceptSession]);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user: session.user,
      expiresAt: session.expires_at,
      login,
      logout,
      refreshSession,
      hasRole: (...roles) => Boolean(session.user && roles.includes(session.user.role)),
    }),
    [login, logout, refreshSession, session.expires_at, session.user, status],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// The provider and its hook intentionally share one module so their private context cannot leak.
// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used within AuthProvider.");
  return value;
}
