import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { User } from '../types';
import { useChatStore } from './chatStore';
import api from '../lib/api';

interface AuthState {
  isAuthenticated: boolean;
  isAuthChecking: boolean;
  user: User | null;
  login: (user: User) => void;
  logout: () => Promise<void>;
  clearAuth: () => void;
  updateUser: (user: Partial<User>) => void;
  checkAuth: () => Promise<void>;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      isAuthenticated: false,
      isAuthChecking: true,
      user: null,
      login: (user) => {
        set({ isAuthenticated: true, user });
        useChatStore.getState().syncGuestMessages();
        useChatStore.getState().resetGuestCount();
      },
      logout: async () => {
        try {
          await api.post('/auth/logout');
        } catch {
          // 서버 로그아웃 실패해도 클라이언트 상태는 초기화
        }
        get().clearAuth();
      },
      clearAuth: () => {
        localStorage.removeItem('accessToken');
        set({ isAuthenticated: false, user: null });
      },
      updateUser: (userData) =>
        set((state) => ({
          user: state.user ? { ...state.user, ...userData } : null,
        })),
      checkAuth: async () => {
        set({ isAuthChecking: true });
        try {
          const response = await api.get('/auth/me');
          const { user } = response.data;
          set({ isAuthenticated: true, user, isAuthChecking: false });
        } catch {
          set({ isAuthenticated: false, user: null, isAuthChecking: false });
        }
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        isAuthenticated: state.isAuthenticated,
        user: state.user,
      }),
    }
  )
);
