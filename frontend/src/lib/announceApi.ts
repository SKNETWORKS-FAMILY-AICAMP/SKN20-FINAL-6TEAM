import api from './api';
import type { AnnounceSyncItem, AnnounceSyncResponse, AnnounceSyncTrigger } from '../types';

const SYNC_ITEM_TYPE = 'info';

const isSyncTrigger = (value: unknown): value is AnnounceSyncTrigger =>
  value === 'login' || value === 'logout';

const normalizeSyncItems = (value: unknown): AnnounceSyncItem[] => {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .filter((item): item is Partial<AnnounceSyncItem> => typeof item === 'object' && item !== null)
    .filter(
      (item): item is AnnounceSyncItem =>
        typeof item.id === 'string' &&
        typeof item.title === 'string' &&
        typeof item.message === 'string' &&
        typeof item.company_label === 'string' &&
        item.type === SYNC_ITEM_TYPE &&
        typeof item.created_at === 'string' &&
        typeof item.link === 'string'
    );
};

export const syncAnnounceNotifications = async (
  trigger: AnnounceSyncTrigger
): Promise<AnnounceSyncResponse> => {
  const response = await api.post('/announces/sync', { trigger });
  const payload = (response.data ?? {}) as Partial<AnnounceSyncResponse>;

  return {
    trigger: isSyncTrigger(payload.trigger) ? payload.trigger : trigger,
    cursor_from: typeof payload.cursor_from === 'string' ? payload.cursor_from : null,
    cursor_to: typeof payload.cursor_to === 'string' ? payload.cursor_to : new Date().toISOString(),
    synced_at: typeof payload.synced_at === 'string' ? payload.synced_at : new Date().toISOString(),
    items: normalizeSyncItems(payload.items),
  };
};
