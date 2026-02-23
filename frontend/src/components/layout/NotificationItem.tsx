import React from 'react';
import { Typography } from '@material-tailwind/react';
import {
  CalendarDaysIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  TrashIcon,
} from '@heroicons/react/24/outline';
import type { Notification } from '../../types';

interface NotificationItemProps {
  notification: Notification;
  onClick: (notification: Notification) => void;
  onDelete: (id: string) => void;
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

export const NotificationItem: React.FC<NotificationItemProps> = ({
  notification,
  onClick,
  onDelete,
}) => {
  const Icon = NOTIFICATION_ICONS[notification.type] ?? InformationCircleIcon;
  const iconColor = NOTIFICATION_ICON_COLORS[notification.type] ?? 'text-gray-500';

  return (
    <div
      className={`flex cursor-pointer items-start gap-3 rounded-lg p-3 transition-colors ${
        notification.is_read ? 'bg-white hover:bg-gray-50' : 'bg-blue-50 hover:bg-blue-100'
      }`}
      onClick={() => onClick(notification)}
      role="button"
      tabIndex={0}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          onClick(notification);
        }
      }}
    >
      <Icon className={`mt-0.5 h-5 w-5 flex-shrink-0 ${iconColor}`} />
      <div className="min-w-0 flex-1">
        <Typography
          variant="small"
          color="blue-gray"
          className={`truncate !text-gray-900 ${!notification.is_read ? 'font-semibold' : ''}`}
        >
          {notification.title}
        </Typography>
        <Typography variant="small" color="gray" className="truncate text-xs !text-gray-700">
          {notification.message}
        </Typography>
        <Typography variant="small" color="gray" className="mt-1 text-xs !text-gray-600">
          {getTimeAgo(notification.created_at)}
        </Typography>
      </div>
      <div className="mt-0.5 flex items-center gap-1">
        {!notification.is_read && (
          <span className="mt-1.5 h-2 w-2 flex-shrink-0 rounded-full bg-blue-500" />
        )}
        <button
          type="button"
          className="rounded p-1 text-gray-400 transition-colors hover:bg-gray-200/70 hover:text-gray-600"
          onClick={(event) => {
            event.stopPropagation();
            onDelete(notification.id);
          }}
          aria-label="Delete notification"
        >
          <TrashIcon className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
};

function getTimeAgo(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);

  if (diffMin < 1) return '\uBC29\uAE08 \uC804';
  if (diffMin < 60) return `${diffMin}\uBD84 \uC804`;
  if (diffHour < 24) return `${diffHour}\uC2DC\uAC04 \uC804`;
  if (diffDay < 7) return `${diffDay}\uC77C \uC804`;
  return date.toLocaleDateString('ko-KR');
}
