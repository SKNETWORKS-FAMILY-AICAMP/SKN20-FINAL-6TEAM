import { useEffect, useRef } from 'react';
import { useNotificationStore } from '../stores/notificationStore';
import type { Notification, Schedule } from '../types';

const DAY_MS = 24 * 60 * 60 * 1000;
const D_7_MS = 7 * DAY_MS;
const D_3_MS = 3 * DAY_MS;

type NotificationDraft = Omit<Notification, 'created_at' | 'is_read'>;

const buildScheduleNotificationDrafts = (schedules: Schedule[]): NotificationDraft[] => {
  const nowTime = Date.now();
  const drafts: NotificationDraft[] = [];

  schedules.forEach((schedule) => {
    const endDateTime = new Date(schedule.end_date).getTime();
    const diffMs = endDateTime - nowTime;

    if (!Number.isFinite(diffMs) || diffMs <= 0) {
      return;
    }

    const daysLeft = Math.ceil(diffMs / DAY_MS);

    if (diffMs <= D_7_MS) {
      drafts.push({
        id: `schedule-d7-${schedule.schedule_id}`,
        title: `D-${daysLeft}: ${schedule.schedule_name}`,
        message: `마감일까지 ${daysLeft}일 남았습니다.`,
        type: 'schedule',
        link: '/schedule',
      });
    }

    if (diffMs <= D_3_MS) {
      drafts.push({
        id: `schedule-d3-${schedule.schedule_id}`,
        title: `긴급 D-${daysLeft}: ${schedule.schedule_name}`,
        message: `마감일까지 ${daysLeft}일 남았습니다. 서둘러 확인하세요!`,
        type: 'warning',
        link: '/schedule',
      });
    }
  });

  return drafts;
};

export const useNotifications = (schedules: Schedule[]) => {
  const lastSignatureRef = useRef<string>('');

  useEffect(() => {
    if (schedules.length === 0) {
      return;
    }

    const drafts = buildScheduleNotificationDrafts(schedules);
    if (drafts.length === 0) {
      return;
    }

    const signature = drafts
      .map((draft) => draft.id)
      .sort()
      .join('|');

    if (lastSignatureRef.current === signature) {
      return;
    }
    lastSignatureRef.current = signature;

    useNotificationStore.setState((state) => {
      const safeNotifications = Array.isArray(state.notifications) ? state.notifications : [];
      const safeToastQueue = Array.isArray(state.toastQueue) ? state.toastQueue : [];
      const existingIds = new Set(safeNotifications.map((notification) => notification.id));

      const draftsToAdd = drafts.filter((draft) => !existingIds.has(draft.id));
      if (draftsToAdd.length === 0) {
        return state;
      }

      const nowIso = new Date().toISOString();
      const newNotifications: Notification[] = draftsToAdd.map((draft) => ({
        ...draft,
        created_at: nowIso,
        is_read: false,
      }));
      const updatedNotifications = [...newNotifications.reverse(), ...safeNotifications];
      const addedIds = newNotifications.map((notification) => notification.id);
      const updatedQueue = [...safeToastQueue, ...addedIds];

      return {
        ...state,
        notifications: updatedNotifications,
        unreadCount: updatedNotifications.filter((notification) => !notification.is_read).length,
        toastQueue: updatedQueue,
        activeToastId: state.activeToastId ?? updatedQueue[0] ?? null,
      };
    });
  }, [schedules]);
};

