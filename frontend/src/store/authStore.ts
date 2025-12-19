import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { authApi, type UserInfo } from '../lib/api.js';

interface AuthState {
  token: string | null;
  user: UserInfo | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<boolean>;
  logout: () => void;
  fetchUser: () => Promise<void>;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: typeof window !== 'undefined' ? localStorage.getItem('route_llm_auth_token') : null,
      user: null,
      loading: false,

      login: async (email: string, password: string) => {
        set({ loading: true });
        try {
          const response = await authApi.login({ email, password });
          const { access_token, must_change_password } = response.data;
          
          localStorage.setItem('route_llm_auth_token', access_token);
          
          // Fetch user info
          const userResponse = await authApi.getCurrentUser();
          
          set({
            token: access_token,
            user: userResponse.data,
            loading: false,
          });
          
          return must_change_password;
        } catch (error) {
          set({ loading: false });
          throw error;
        }
      },

      logout: () => {
        localStorage.removeItem('route_llm_auth_token');
        set({ token: null, user: null });
      },

      fetchUser: async () => {
        const { token } = get();
        if (!token) return;
        
        try {
          const response = await authApi.getCurrentUser();
          set({ user: response.data });
        } catch (error) {
          // Token invalid, logout
          get().logout();
        }
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({ token: state.token }),
    }
  )
);
