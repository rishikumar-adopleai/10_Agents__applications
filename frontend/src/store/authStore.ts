import { create } from 'zustand';
import { User } from '@/types/auth';
import { apiClient } from '@/lib/apiClient';

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  isInitialized: boolean;
  setAuth: (user: User, token: string) => void;
  setUser: (user: User) => void;
  logout: () => void;
  setLoading: (loading: boolean) => void;
  setInitialized: (initialized: boolean) => void;
}

export const useAuthStore = create<AuthState>((set) => {
  // Listen for global logout event dispatched by apiClient refresh failures
  if (typeof window !== 'undefined') {
    window.addEventListener('auth:logout', () => {
      delete apiClient.defaults.headers.common['Authorization'];
      set({ user: null, token: null, isAuthenticated: false, isLoading: false });
    });
  }

  return {
    user: null,
    token: null,
    isAuthenticated: false,
    isLoading: true,
    isInitialized: false,

    setAuth: (user, token) => {
      apiClient.defaults.headers.common['Authorization'] = `Bearer ${token}`;
      set({ user, token, isAuthenticated: true, isLoading: false, isInitialized: true });
    },

    setUser: (user) => {
      set({ user });
    },

    logout: () => {
      delete apiClient.defaults.headers.common['Authorization'];
      set({ user: null, token: null, isAuthenticated: false, isLoading: false });
    },

    setLoading: (loading) => {
      set({ isLoading: loading });
    },

    setInitialized: (initialized) => {
      set({ isInitialized: initialized, isLoading: false });
    },
  };
});
