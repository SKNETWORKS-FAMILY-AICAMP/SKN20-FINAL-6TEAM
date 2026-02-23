import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Typography } from '@material-tailwind/react';
import {
  CalendarDaysIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';
import type { Notification } from '../../types';

const TOAST_AUTO_HIDE_MS = 3000;
const TOAST_EXIT_ANIMATION_MS = 220;

interface NotificationToastProps {
  notification: Notification;
  onClose: () => void;
  placement?: 'top-center' | 'bell-side';
  stackIndex?: number;
}

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

export const NotificationToast: React.FC<NotificationToastProps> = ({
  notification,
  onClose,
  placement = 'top-center',
  stackIndex = 0,
}) => {
  const [isVisible, setIsVisible] = useState(false);
  const isClosingRef = useRef(false);

  const closeToast = useCallback(() => {
    if (isClosingRef.current) {
      return;
    }

    isClosingRef.current = true;
    setIsVisible(false);
    window.setTimeout(() => {
      onClose();
    }, TOAST_EXIT_ANIMATION_MS);
  }, [onClose]);

  useEffect(() => {
    isClosingRef.current = false;

    const rafId = window.requestAnimationFrame(() => {
      setIsVisible(true);
    });
    const timerId = window.setTimeout(() => {
      closeToast();
    }, TOAST_AUTO_HIDE_MS);

    return () => {
      window.cancelAnimationFrame(rafId);
      window.clearTimeout(timerId);
    };
  }, [notification.id, closeToast]);

  const Icon = NOTIFICATION_ICONS[notification.type] ?? InformationCircleIcon;
  const iconColor = NOTIFICATION_ICON_COLORS[notification.type] ?? 'text-gray-500';
  const bellBaseTopPx = 52;
  const bellStackGapPx = 68;
  const containerClassName =
    placement === 'bell-side'
      ? 'pointer-events-none fixed right-3 z-[70] w-[min(92vw,22rem)] sm:right-6'
      : 'pointer-events-none fixed left-1/2 top-4 z-[70] w-full -translate-x-1/2 px-3';
  const containerStyle =
    placement === 'bell-side'
      ? { top: `${bellBaseTopPx + stackIndex * bellStackGapPx}px` }
      : undefined;
  const panelClassName =
    placement === 'bell-side'
      ? 'pointer-events-auto w-full rounded-xl border border-gray-200 bg-white px-4 py-3 shadow-xl transition-all duration-200'
      : 'pointer-events-auto mx-auto w-full max-w-md rounded-xl border border-gray-200 bg-white px-4 py-3 shadow-xl transition-all duration-200';

  return (
    <div className={containerClassName} style={containerStyle}>
      <div
        className={`${panelClassName} ${
          isVisible ? 'translate-y-0 opacity-100' : '-translate-y-3 opacity-0'
        }`}
      >
        <div className="flex items-start gap-3">
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
            onClick={closeToast}
            className="rounded p-1 text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-700"
            aria-label="Close notification"
          >
            <XMarkIcon className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
};
