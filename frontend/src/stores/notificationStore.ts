import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { Notification } from '../types';

const NOTIFICATION_TYPES = ['schedule', 'info', 'warning'] as const;

const isNotificationType = (value: unknown): value is Notification['type'] =>
  typeof value === 'string' &&
  (NOTIFICATION_TYPES as readonly string[]).includes(value);

const normalizeNotifications = (value: unknown): Notification[] => {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .filter((item): item is Partial<Notification> => typeof item === 'object' && item !== null)
    .map((item) => ({
      id: typeof item.id === 'string' ? item.id : `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      title: typeof item.title === 'string' ? item.title : '',
      message: typeof item.message === 'string' ? item.message : '',
      type: isNotificationType(item.type) ? item.type : 'info',
      is_read: typeof item.is_read === 'boolean' ? item.is_read : false,
      created_at:
        typeof item.created_at === 'string' ? item.created_at : new Date().toISOString(),
      link: typeof item.link === 'string' ? item.link : undefined,
    }));
};

interface NotificationState {
  notifications: Notification[];
  unreadCount: number;
  toastQueue: string[];
  activeToastId: string | null;
  addNotification: (
    notification: Omit<Notification, 'id' | 'created_at' | 'is_read'> & { id?: string }
  ) => void;
  markAsRead: (id: string) => void;
  markAllAsRead: () => void;
  removeNotification: (id: string) => void;
  dismissToast: (id: string) => void;
  dequeueToast: () => void;
  clearAllNotifications: () => void;
}

export const useNotificationStore = create<NotificationState>()(
  persist(
    (set) => ({
      notifications: [],
      unreadCount: 0,
      toastQueue: [],
      activeToastId: null,
      addNotification: (notification) =>
        set((state) => {
          const safeNotifications = Array.isArray(state.notifications) ? state.notifications : [];
          const safeToastQueue = Array.isArray(state.toastQueue) ? state.toastQueue : [];
          const { id: customId, ...notificationPayload } = notification;
          const notificationId =
            customId ?? `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

          if (safeNotifications.some((n) => n.id === notificationId)) {
            return state;
          }

          const newNotification: Notification = {
            ...notificationPayload,
            id: notificationId,
            created_at: new Date().toISOString(),
            is_read: false,
          };
          const updatedNotifications = [newNotification, ...safeNotifications];
          const updatedQueue = [...safeToastQueue, notificationId];

          return {
            notifications: updatedNotifications,
            unreadCount: updatedNotifications.filter((n) => !n.is_read).length,
            toastQueue: updatedQueue,
            activeToastId: state.activeToastId ?? updatedQueue[0] ?? null,
          };
        }),
      markAsRead: (id) =>
        set((state) => {
          const safeNotifications = Array.isArray(state.notifications) ? state.notifications : [];
          const updatedNotifications = safeNotifications.map((n) =>
            n.id === id ? { ...n, is_read: true } : n
          );
          return {
            notifications: updatedNotifications,
            unreadCount: updatedNotifications.filter((n) => !n.is_read).length,
          };
        }),
      markAllAsRead: () =>
        set((state) => ({
          notifications: (Array.isArray(state.notifications) ? state.notifications : []).map((n) => ({
            ...n,
            is_read: true,
          })),
          unreadCount: 0,
        })),
      removeNotification: (id) =>
        set((state) => {
          const safeNotifications = Array.isArray(state.notifications) ? state.notifications : [];
          const safeToastQueue = Array.isArray(state.toastQueue) ? state.toastQueue : [];
          const updatedNotifications = safeNotifications.filter((n) => n.id !== id);
          const updatedQueue = safeToastQueue.filter((toastId) => toastId !== id);
          const nextActiveToastId =
            state.activeToastId === id ? updatedQueue[0] ?? null : state.activeToastId;

          return {
            notifications: updatedNotifications,
            unreadCount: updatedNotifications.filter((n) => !n.is_read).length,
            toastQueue: updatedQueue,
            activeToastId: nextActiveToastId,
          };
        }),
      dismissToast: (id) =>
        set((state) => {
          const safeToastQueue = Array.isArray(state.toastQueue) ? state.toastQueue : [];
          const hasTarget = safeToastQueue.includes(id) || state.activeToastId === id;
          if (!hasTarget) {
            return state;
          }

          const updatedQueue = safeToastQueue.filter((toastId) => toastId !== id);
          const nextActiveToastId =
            state.activeToastId === id ? updatedQueue[0] ?? null : state.activeToastId;

          return {
            toastQueue: updatedQueue,
            activeToastId: nextActiveToastId,
          };
        }),
      dequeueToast: () =>
        set((state) => {
          const safeToastQueue = Array.isArray(state.toastQueue) ? state.toastQueue : [];

          if (!state.activeToastId && safeToastQueue.length === 0) {
            return state;
          }

          const remainingQueue = state.activeToastId
            ? safeToastQueue.filter((id) => id !== state.activeToastId)
            : [...safeToastQueue];
          const nextActiveToastId = remainingQueue[0] ?? null;

          return {
            toastQueue: remainingQueue,
            activeToastId: nextActiveToastId,
          };
        }),
      clearAllNotifications: () =>
        set(() => ({
          notifications: [],
          unreadCount: 0,
          toastQueue: [],
          activeToastId: null,
        })),
    }),
    {
      name: 'notification-storage',
      partialize: (state) => ({
        notifications: state.notifications,
        unreadCount: state.unreadCount,
      }),
      merge: (persistedState, currentState) => {
        const persisted = (persistedState as Partial<NotificationState> | null) ?? {};
        const notifications = normalizeNotifications(persisted.notifications);
        const unreadCount =
          typeof persisted.unreadCount === 'number'
            ? persisted.unreadCount
            : notifications.filter((notification) => !notification.is_read).length;

        return {
          ...currentState,
          notifications,
          unreadCount,
          toastQueue: Array.isArray(persisted.toastQueue) ? persisted.toastQueue : [],
          activeToastId:
            typeof persisted.activeToastId === 'string' ? persisted.activeToastId : null,
        };
      },
    }
  )
);
