import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { syncAnnounceNotifications } from '../lib/announceApi';
import api from '../lib/api';
import { DEFAULT_NOTIFICATION_SETTINGS } from '../lib/constants';
import { getNotificationSettings } from '../lib/userApi';
import type { AnnounceSyncTrigger, NotificationSettings, User } from '../types';
import { useChatStore } from './chatStore';
import { useNotificationStore } from './notificationStore';

const AUTH_CHECK_DEDUP_MS = 3000;
const ANNOUNCE_SYNC_LOGOUT_MAX_WAIT_MS = 1500;
let authCheckInFlight: Promise<void> | null = null;
let lastAuthCheckAt = 0;

interface AuthState {
  isAuthenticated: boolean;
  isAuthChecking: boolean;
  user: User | null;
  notificationSettings: NotificationSettings;
  notificationSettingsLoaded: boolean;
  login: (user: User) => Promise<void>;
  logout: () => Promise<void>;
  clearAuth: () => void;
  updateUser: (user: Partial<User>) => void;
  setNotificationSettings: (settings: NotificationSettings) => void;
  checkAuth: () => Promise<void>;
}

const waitFor = (ms: number): Promise<void> =>
  new Promise((resolve) => {
    setTimeout(resolve, ms);
  });

const syncAnnounceNotificationsToStore = async (
  trigger: AnnounceSyncTrigger
): Promise<void> => {
  try {
    const response = await syncAnnounceNotifications(trigger);
    const addNotification = useNotificationStore.getState().addNotification;

    response.items.forEach((item) => {
      addNotification({
        id: item.id,
        title: item.title,
        message: item.message,
        company_label: item.company_label,
        type: item.type,
        created_at: item.created_at,
        link: item.link,
      });
    });
  } catch (error) {
    console.error(`Failed to sync announce notifications (${trigger}):`, error);
  }
};

const fetchNotificationSettingsSafely = async (): Promise<NotificationSettings> => {
  try {
    return await getNotificationSettings();
  } catch (error) {
    console.error('Failed to fetch notification settings:', error);
    return { ...DEFAULT_NOTIFICATION_SETTINGS };
  }
};

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      isAuthenticated: false,
      isAuthChecking: true,
      user: null,
      notificationSettings: { ...DEFAULT_NOTIFICATION_SETTINGS },
      notificationSettingsLoaded: false,
      login: async (user) => {
        set({
          isAuthenticated: true,
          user,
          notificationSettingsLoaded: false,
        });
        useNotificationStore.getState().bindOwner(user.user_id);
        const settings = await fetchNotificationSettingsSafely();
        set({
          notificationSettings: settings,
          notificationSettingsLoaded: true,
        });
        void syncAnnounceNotificationsToStore('login');
        await useChatStore.getState().syncGuestMessages();
        useChatStore.getState().resetGuestCount();
        await useChatStore.getState().bootstrapFromServerHistories();
      },
      logout: async () => {
        const logoutSyncPromise = syncAnnounceNotificationsToStore('logout');
        await Promise.race([
          logoutSyncPromise,
          waitFor(ANNOUNCE_SYNC_LOGOUT_MAX_WAIT_MS),
        ]);

        try {
          await api.post('/auth/logout');
        } catch {
          // 서버 로그아웃 실패여도 클라이언트 상태는 초기화합니다.
        }
        get().clearAuth();
      },
      clearAuth: () => {
        set({
          isAuthenticated: false,
          user: null,
          notificationSettings: { ...DEFAULT_NOTIFICATION_SETTINGS },
          notificationSettingsLoaded: false,
        });
        // 로그아웃 시 chatStore 세션 초기화 (재로그인 시 중복 저장 방지)
        useChatStore.getState().resetOnLogout();
      },
      updateUser: (userData) =>
        set((state) => ({
          user: state.user ? { ...state.user, ...userData } : null,
        })),
      setNotificationSettings: (settings) =>
        set({
          notificationSettings: settings,
          notificationSettingsLoaded: true,
        }),
      checkAuth: async () => {
        if (authCheckInFlight) {
          await authCheckInFlight;
          return;
        }

        const now = Date.now();
        if (now - lastAuthCheckAt < AUTH_CHECK_DEDUP_MS) {
          return;
        }

        set({ isAuthChecking: true });

        authCheckInFlight = (async () => {
          try {
            const response = await api.get('/auth/me');
            const { user } = response.data;
            const settings = await fetchNotificationSettingsSafely();
            set({
              isAuthenticated: true,
              user,
              notificationSettings: settings,
              notificationSettingsLoaded: true,
            });
            useNotificationStore.getState().bindOwner(user.user_id);
            useChatStore.getState().bootstrapFromServerHistories();
          } catch {
            set({
              isAuthenticated: false,
              user: null,
              notificationSettings: { ...DEFAULT_NOTIFICATION_SETTINGS },
              notificationSettingsLoaded: false,
            });
          } finally {
            set({ isAuthChecking: false });
            lastAuthCheckAt = Date.now();
            authCheckInFlight = null;
          }
        })();

        await authCheckInFlight;
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
