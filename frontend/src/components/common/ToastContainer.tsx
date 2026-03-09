import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Typography } from '@material-tailwind/react';
import {
  XMarkIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
  CalendarDaysIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
} from '@heroicons/react/24/outline';
import { useToastStore } from '../../stores/toastStore';
import { useNotificationStore } from '../../stores/notificationStore';
import type { Notification } from '../../types';

const ACTION_AUTO_HIDE_MS = 3300;
const NOTIFICATION_AUTO_HIDE_MS = 3000;
const EXIT_MS = 400;

// ── Unified toast type ──

type UnifiedToast =
  | { kind: 'action'; id: string; type: 'success' | 'error'; message: string; autoHideMs: number }
  | { kind: 'notification'; id: string; notification: Notification; autoHideMs: number };

// ── Individual toast items ──

const NOTIFICATION_ICONS: Record<Notification['type'], React.ElementType> = {
  schedule: CalendarDaysIcon,
  info: InformationCircleIcon,
  warning: ExclamationTriangleIcon,
};

const NOTIFICATION_ICON_COLORS: Record<Notification['type'], string> = {
  schedule: 'text-blue-500',
  info: 'text-gray-500',
  warning: 'text-orange-500',
};

type Phase = 'entering' | 'visible' | 'exiting';

interface ToastItemWrapperProps {
  item: UnifiedToast;
  onRemove: (id: string) => void;
}

const ToastItemWrapper: React.FC<ToastItemWrapperProps> = ({ item, onRemove }) => {
  const [phase, setPhase] = useState<Phase>('entering');
  const isClosingRef = useRef(false);

  const close = useCallback(() => {
    if (isClosingRef.current) return;
    isClosingRef.current = true;
    setPhase('exiting');
  }, []);

  // Phase transitions
  useEffect(() => {
    if (phase === 'entering') {
      const rafId = window.requestAnimationFrame(() => setPhase('visible'));
      return () => window.cancelAnimationFrame(rafId);
    }
    if (phase === 'exiting') {
      const id = window.setTimeout(() => onRemove(item.id), EXIT_MS);
      return () => window.clearTimeout(id);
    }
  }, [phase, item.id, onRemove]);

  // Auto-hide timer
  useEffect(() => {
    const timerId = window.setTimeout(close, item.autoHideMs);
    return () => window.clearTimeout(timerId);
  }, [item.id, close, item.autoHideMs]);

  const fadeClass = phase === 'visible'
    ? 'opacity-100'
    : 'opacity-0';

  if (item.kind === 'action') {
    const isSuccess = item.type === 'success';
    const Icon = isSuccess ? CheckCircleIcon : ExclamationCircleIcon;
    const colorClass = isSuccess
      ? 'border-green-200 bg-green-50 text-green-800'
      : 'border-red-200 bg-red-50 text-red-800';
    const iconClass = isSuccess ? 'text-green-500' : 'text-red-500';

    return (
      <div
        className={`pointer-events-auto flex items-start gap-3 rounded-xl border px-4 py-3 shadow-xl transition-opacity duration-400 ease-in-out ${colorClass} ${fadeClass}`}
      >
        <Icon className={`mt-0.5 h-5 w-5 flex-shrink-0 ${iconClass}`} />
        <span className="flex-1 text-sm font-medium">{item.message}</span>
        <button
          type="button"
          onClick={close}
          className="rounded p-1 opacity-60 transition-colors hover:opacity-100"
          aria-label="닫기"
        >
          <XMarkIcon className="h-4 w-4" />
        </button>
      </div>
    );
  }

  // Notification toast
  const { notification } = item;
  const Icon = NOTIFICATION_ICONS[notification.type] ?? InformationCircleIcon;
  const iconColor = NOTIFICATION_ICON_COLORS[notification.type] ?? 'text-gray-500';

  return (
    <div
      className={`pointer-events-auto flex items-start gap-3 rounded-xl border border-gray-200 bg-white px-4 py-3 shadow-xl transition-opacity duration-400 ease-in-out ${fadeClass}`}
    >
      <Icon className={`mt-0.5 h-5 w-5 flex-shrink-0 ${iconColor}`} />
      <div className="min-w-0 flex-1">
        <Typography variant="small" color="blue-gray" className="truncate font-semibold !text-gray-900">
          {notification.title}
        </Typography>
        <Typography variant="small" color="gray" className="mt-0.5 truncate text-xs !text-gray-700">
          {notification.message}
        </Typography>
      </div>
      <button
        type="button"
        onClick={close}
        className="rounded p-1 text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-700"
        aria-label="닫기"
      >
        <XMarkIcon className="h-4 w-4" />
      </button>
    </div>
  );
};

// ── Container ──

export const ToastContainer: React.FC = () => {
  const { toasts, removeToast } = useToastStore();
  const { notifications, toastQueue, dismissToast } = useNotificationStore();

  const items: UnifiedToast[] = [];

  for (const toast of toasts) {
    items.push({
      kind: 'action',
      id: `action-${toast.id}`,
      type: toast.type,
      message: toast.message,
      autoHideMs: ACTION_AUTO_HIDE_MS,
    });
  }

  for (const toastId of toastQueue) {
    const notification = notifications.find((n) => n.id === toastId);
    if (notification) {
      items.push({
        kind: 'notification',
        id: `notif-${notification.id}`,
        notification,
        autoHideMs: NOTIFICATION_AUTO_HIDE_MS,
      });
    }
  }

  const handleRemove = useCallback(
    (unifiedId: string) => {
      if (unifiedId.startsWith('action-')) {
        removeToast(unifiedId.slice(7));
      } else if (unifiedId.startsWith('notif-')) {
        dismissToast(unifiedId.slice(6));
      }
    },
    [removeToast, dismissToast]
  );

  if (items.length === 0) return null;

  return (
    <div className="pointer-events-none fixed right-4 top-4 z-[9999] flex w-[min(92vw,26rem)] flex-col gap-2">
      {items.map((item) => (
        <ToastItemWrapper key={item.id} item={item} onRemove={handleRemove} />
      ))}
    </div>
  );
};
