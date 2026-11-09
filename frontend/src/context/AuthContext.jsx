import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import {
  ACCESS_TOKEN_KEY,
  authApi,
  clearTokens,
  getAccessToken,
  storeTokens,
} from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [accessToken, setAccessToken] = useState(() => getAccessToken());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    const token = getAccessToken();

    if (!token) {
      setLoading(false);
      return undefined;
    }

    authApi
      .me()
      .then(({ data }) => {
        if (active) setUser(data);
      })
      .catch(() => {
        clearTokens();
        if (active) {
          setUser(null);
          setAccessToken(null);
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    const handleTokens = (event) => {
      setAccessToken(event.detail?.access || getAccessToken());
    };
    const handleLogout = () => {
      setUser(null);
      setAccessToken(null);
    };
    window.addEventListener('auth:tokens', handleTokens);
    window.addEventListener('auth:logout', handleLogout);
    return () => {
      window.removeEventListener('auth:tokens', handleTokens);
      window.removeEventListener('auth:logout', handleLogout);
    };
  }, []);

  const login = useCallback(async (username, password) => {
    const { data } = await authApi.login({ username, password });
    storeTokens(data);
    setAccessToken(data.access);
    setUser(data.user);
    return data.user;
  }, []);

  const logout = useCallback(() => {
    clearTokens();
    setUser(null);
    setAccessToken(null);
  }, []);

  const value = useMemo(
    () => ({ user, accessToken, loading, login, logout }),
    [user, accessToken, loading, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used inside an AuthProvider.');
  return context;
}

export { ACCESS_TOKEN_KEY };
