import { useEffect, useRef } from 'react';
import { useNotificationStore } from '../stores/notificationStore';
import type { Notification, Schedule } from '../types';

const DAY_MS = 24 * 60 * 60 * 1000;
const D_7_MS = 7 * DAY_MS;
const D_3_MS = 3 * DAY_MS;
const SCHEDULE_D7_PREFIX = 'schedule-d7-';
const SCHEDULE_D3_PREFIX = 'schedule-d3-';

type NotificationDraft = Omit<Notification, 'created_at' | 'is_read'>;
type CompanyNameById = Record<number, string>;

const extractScheduleIdFromNotificationId = (
  notificationId: string,
  prefix: string
): number | null => {
  if (!notificationId.startsWith(prefix)) {
    return null;
  }

  const parsed = Number.parseInt(notificationId.slice(prefix.length), 10);
  return Number.isNaN(parsed) ? null : parsed;
};

const buildCompanyLabel = (schedule: Schedule, companyNameById: CompanyNameById): string => {
  const companyName = companyNameById[schedule.company_id];
  return companyName ?? `\uAE30\uC5C5 #${schedule.company_id}`;
};

const buildScheduleNotificationDrafts = (
  schedules: Schedule[],
  companyNameById: CompanyNameById
): NotificationDraft[] => {
  const nowTime = Date.now();
  const drafts: NotificationDraft[] = [];

  schedules.forEach((schedule) => {
    const endDateTime = new Date(schedule.end_date).getTime();
    const diffMs = endDateTime - nowTime;

    if (!Number.isFinite(diffMs) || diffMs <= 0) {
      return;
    }

    const daysLeft = Math.ceil(diffMs / DAY_MS);
    const companyLabel = buildCompanyLabel(schedule, companyNameById);

    if (diffMs <= D_3_MS) {
      drafts.push({
        id: `${SCHEDULE_D3_PREFIX}${schedule.schedule_id}`,
        title: `\uAE34\uAE09 D-${daysLeft}: ${schedule.schedule_name}`,
        message: `\uB9C8\uAC10 ${daysLeft}\uC77C \uC804\uC785\uB2C8\uB2E4. \uC9C0\uAE08 \uD655\uC778\uD558\uC138\uC694.`,
        company_label: companyLabel,
        type: 'warning',
        link: '/schedule',
      });
      return;
    }

    if (diffMs <= D_7_MS) {
      drafts.push({
        id: `${SCHEDULE_D7_PREFIX}${schedule.schedule_id}`,
        title: `D-${daysLeft}: ${schedule.schedule_name}`,
        message: `\uB9C8\uAC10 ${daysLeft}\uC77C \uC804\uC785\uB2C8\uB2E4.`,
        company_label: companyLabel,
        type: 'schedule',
        link: '/schedule',
      });
    }
  });

  return drafts;
};

export const useNotifications = (
  schedules: Schedule[],
  companyNameById: CompanyNameById = {}
) => {
  const lastSignatureRef = useRef<string>('');

  useEffect(() => {
    if (schedules.length === 0) {
      lastSignatureRef.current = '';
      return;
    }

    const drafts = buildScheduleNotificationDrafts(schedules, companyNameById);
    if (drafts.length === 0) {
      lastSignatureRef.current = '';
      return;
    }

    const signature = drafts
      .map((draft) => `${draft.id}:${draft.title}:${draft.message}:${draft.company_label ?? ''}`)
      .sort()
      .join('|');

    if (lastSignatureRef.current === signature) {
      return;
    }
    lastSignatureRef.current = signature;

    useNotificationStore.setState((state) => {
      const safeNotifications = Array.isArray(state.notifications) ? state.notifications : [];
      const safeToastQueue = Array.isArray(state.toastQueue) ? state.toastQueue : [];
      const urgentScheduleIds = new Set(
        drafts
          .map((draft) => extractScheduleIdFromNotificationId(draft.id, SCHEDULE_D3_PREFIX))
          .filter((scheduleId): scheduleId is number => scheduleId !== null)
      );

      const redundantNotificationIds = new Set(
        safeNotifications
          .filter((notification) => {
            const scheduleId = extractScheduleIdFromNotificationId(
              notification.id,
              SCHEDULE_D7_PREFIX
            );
            return scheduleId !== null && urgentScheduleIds.has(scheduleId);
          })
          .map((notification) => notification.id)
      );

      const cleanedNotifications = safeNotifications.filter(
        (notification) => !redundantNotificationIds.has(notification.id)
      );
      const cleanedQueue = safeToastQueue.filter(
        (notificationId) => !redundantNotificationIds.has(notificationId)
      );
      const existingIds = new Set(cleanedNotifications.map((notification) => notification.id));
      const draftsToAdd = drafts.filter((draft) => !existingIds.has(draft.id));

      if (draftsToAdd.length === 0 && redundantNotificationIds.size === 0) {
        return state;
      }

      const nowIso = new Date().toISOString();
      const newNotifications: Notification[] = draftsToAdd.map((draft) => ({
        ...draft,
        created_at: nowIso,
        is_read: false,
      }));
      const updatedNotifications = [...newNotifications.reverse(), ...cleanedNotifications];
      const addedIds = newNotifications.map((notification) => notification.id);
      const updatedQueue = [...cleanedQueue, ...addedIds];
      const activeToastId =
        state.activeToastId && !redundantNotificationIds.has(state.activeToastId)
          ? state.activeToastId
          : null;

      return {
        ...state,
        notifications: updatedNotifications,
        unreadCount: updatedNotifications.filter((notification) => !notification.is_read).length,
        toastQueue: updatedQueue,
        activeToastId: activeToastId ?? updatedQueue[0] ?? null,
      };
    });
  }, [schedules, companyNameById]);
};
