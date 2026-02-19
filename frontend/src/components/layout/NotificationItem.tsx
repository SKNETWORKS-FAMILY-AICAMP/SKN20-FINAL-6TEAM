import React from 'react';
import { Typography } from '@material-tailwind/react';
import {
  CalendarDaysIcon,
  InformationCircleIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/outline';
import type { Notification } from '../../types';

interface NotificationItemProps {
  notification: Notification;
  onClick: (notification: Notification) => void;
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
}) => {
  const Icon = NOTIFICATION_ICONS[notification.type];
  const iconColor = NOTIFICATION_ICON_COLORS[notification.type];

  const timeAgo = getTimeAgo(notification.created_at);

  return (
    <div
      className={`flex items-start gap-3 p-3 cursor-pointer transition-colors rounded-lg ${
        notification.is_read ? 'bg-white hover:bg-gray-50' : 'bg-blue-50 hover:bg-blue-100'
      }`}
      onClick={() => onClick(notification)}
    >
      <Icon className={`h-5 w-5 mt-0.5 flex-shrink-0 ${iconColor}`} />
      <div className="flex-1 min-w-0">
        <Typography
          variant="small"
          color="blue-gray"
          className={`truncate !text-gray-900 ${!notification.is_read ? 'font-semibold' : ''}`}
        >
          {notification.title}
        </Typography>
        <Typography variant="small" color="gray" className="text-xs truncate !text-gray-700">
          {notification.message}
        </Typography>
        <Typography variant="small" color="gray" className="text-xs mt-1 !text-gray-600">
          {timeAgo}
        </Typography>
      </div>
      {!notification.is_read && (
        <div className="w-2 h-2 bg-blue-500 rounded-full flex-shrink-0 mt-2" />
      )}
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

  if (diffMin < 1) return '방금 전';
  if (diffMin < 60) return `${diffMin}분 전`;
  if (diffHour < 24) return `${diffHour}시간 전`;
  if (diffDay < 7) return `${diffDay}일 전`;
  return date.toLocaleDateString('ko-KR');
}
