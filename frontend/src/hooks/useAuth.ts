import { useState, useEffect } from 'react';
import { login, getCurrentUser } from '../api/client';
import type { UserInfo } from '../api/client';

const TOKEN_KEY = 'route_llm_auth_token';

export function useAuth() {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<UserInfo | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const storedToken = localStorage.getItem(TOKEN_KEY);
    if (storedToken) {
      setToken(storedToken);
      // Verify token by fetching user info
      getCurrentUser(storedToken)
        .then(setUser)
        .catch(() => {
          // Token invalid, clear it
          localStorage.removeItem(TOKEN_KEY);
          setToken(null);
        })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const handleLogin = async (email: string, password: string) => {
    const response = await login({ email, password });
    localStorage.setItem(TOKEN_KEY, response.access_token);
    setToken(response.access_token);
    const userInfo = await getCurrentUser(response.access_token);
    setUser(userInfo);
    return response.must_change_password;
  };

  const handleLogout = () => {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
  };

  return { token, user, loading, handleLogin, handleLogout };
}

