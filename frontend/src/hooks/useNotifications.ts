import { useEffect } from 'react';
import { useNotificationStore } from '../stores/notificationStore';
import type { Schedule } from '../types';

const D_7_MS = 7 * 24 * 60 * 60 * 1000;
const D_3_MS = 3 * 24 * 60 * 60 * 1000;

export const useNotifications = (schedules: Schedule[]) => {
  const { addNotification, notifications } = useNotificationStore();

  useEffect(() => {
    if (schedules.length === 0) return;

    const now = new Date();

    schedules.forEach((schedule) => {
      const endDate = new Date(schedule.end_date);
      const diffMs = endDate.getTime() - now.getTime();

      // D-7 notification
      if (diffMs > 0 && diffMs <= D_7_MS) {
        const notifId = `schedule-d7-${schedule.schedule_id}`;
        const alreadyExists = notifications.some((n) => n.id === notifId);
        if (!alreadyExists) {
          const daysLeft = Math.ceil(diffMs / (24 * 60 * 60 * 1000));
          addNotification({
            title: `D-${daysLeft}: ${schedule.schedule_name}`,
            message: `마감일이 ${daysLeft}일 남았습니다.`,
            type: 'schedule',
            link: '/schedule',
          });
        }
      }

      // D-3 notification (higher priority)
      if (diffMs > 0 && diffMs <= D_3_MS) {
        const notifId = `schedule-d3-${schedule.schedule_id}`;
        const alreadyExists = notifications.some((n) => n.id === notifId);
        if (!alreadyExists) {
          const daysLeft = Math.ceil(diffMs / (24 * 60 * 60 * 1000));
          addNotification({
            title: `긴급 D-${daysLeft}: ${schedule.schedule_name}`,
            message: `마감일이 ${daysLeft}일 남았습니다. 서둘러 확인해주세요!`,
            type: 'warning',
            link: '/schedule',
          });
        }
      }
    });
  }, [schedules, addNotification, notifications]);
};
