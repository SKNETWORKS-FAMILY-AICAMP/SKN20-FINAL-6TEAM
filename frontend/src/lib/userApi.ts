import api from './api';
import { DEFAULT_NOTIFICATION_SETTINGS } from './constants';
import type { NotificationSettings } from '../types';

const normalizeNotificationSettings = (value: unknown): NotificationSettings => {
  const defaults = DEFAULT_NOTIFICATION_SETTINGS;
  if (typeof value !== 'object' || value === null) {
    return { ...defaults };
  }

  const payload = value as Partial<NotificationSettings>;
  return {
    schedule_d7:
      typeof payload.schedule_d7 === 'boolean' ? payload.schedule_d7 : defaults.schedule_d7,
    schedule_d3:
      typeof payload.schedule_d3 === 'boolean' ? payload.schedule_d3 : defaults.schedule_d3,
    new_announce:
      typeof payload.new_announce === 'boolean'
        ? payload.new_announce
        : defaults.new_announce,
    answer_complete:
      typeof payload.answer_complete === 'boolean'
        ? payload.answer_complete
        : defaults.answer_complete,
  };
};

export const getNotificationSettings = async (): Promise<NotificationSettings> => {
  const response = await api.get('/users/me/notification-settings');
  return normalizeNotificationSettings(response.data);
};

export const updateNotificationSettings = async (
  settings: NotificationSettings
): Promise<NotificationSettings> => {
  const payload = normalizeNotificationSettings(settings);
  const response = await api.put('/users/me/notification-settings', payload);
  return normalizeNotificationSettings(response.data);
};

