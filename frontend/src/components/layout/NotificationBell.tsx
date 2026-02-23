import React, { useEffect, useRef, useState } from 'react';
import { Typography } from '@material-tailwind/react';
import { BellIcon } from '@heroicons/react/24/outline';
import { BellIcon as BellIconSolid } from '@heroicons/react/24/solid';
import { useNavigate } from 'react-router-dom';
import { useNotificationStore } from '../../stores/notificationStore';
import { NotificationItem } from './NotificationItem';
import type { Notification } from '../../types';

const SCROLL_THRESHOLD_COUNT = 4;

export const NotificationBell: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const popoverRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  const {
    notifications,
    unreadCount,
    markAsRead,
    markAllAsRead,
    removeNotification,
    clearAllNotifications,
  } = useNotificationStore();

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  const handleBellClick = () => {
    const willOpen = !isOpen;
    setIsOpen(willOpen);
    if (willOpen) {
      markAllAsRead();
    }
  };

  const handleNotificationClick = (notification: Notification) => {
    if (!notification.is_read) {
      markAsRead(notification.id);
    }

    if (notification.link) {
      navigate(notification.link);
      setIsOpen(false);
    }
  };

  const shouldScroll = notifications.length > SCROLL_THRESHOLD_COUNT;

  return (
    <div className="relative" ref={popoverRef}>
      <button
        type="button"
        className={`relative rounded-full p-1 transition-colors ${
          isOpen ? 'bg-blue-50' : 'hover:bg-gray-100'
        }`}
        onClick={handleBellClick}
        aria-label="Open notifications"
      >
        {isOpen ? (
          <BellIconSolid className="h-5 w-5 text-blue-600" />
        ) : (
          <BellIcon className="h-5 w-5 text-gray-600" />
        )}
        {unreadCount > 0 && (
          <span className="absolute -right-1 -top-1 flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-red-500 px-1 text-[10px] text-white">
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {isOpen && (
        <div className="absolute right-0 top-full z-50 mt-2 flex w-80 flex-col overflow-hidden rounded-lg border bg-white shadow-xl">
          <div className="flex items-center justify-between border-b p-3">
            <Typography variant="small" color="blue-gray" className="font-semibold !text-gray-900">
              {'\uC54C\uB9BC'}
            </Typography>
            {notifications.length > 0 && (
              <button
                type="button"
                className="rounded px-2 py-1 text-xs text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-700"
                onClick={clearAllNotifications}
              >
                {'\uC804\uCCB4 \uC0AD\uC81C'}
              </button>
            )}
          </div>

          <div
            className={`flex-1 ${shouldScroll ? 'max-h-[19rem] overflow-y-auto p-2' : 'p-2'}`}
          >
            {notifications.length === 0 ? (
              <div className="p-5 text-center">
                <Typography variant="small" color="gray" className="!text-gray-600">
                  {'\uC54C\uB9BC\uC774 \uC5C6\uC2B5\uB2C8\uB2E4.'}
                </Typography>
              </div>
            ) : (
              <div className="space-y-1">
                {notifications.map((notification) => (
                  <NotificationItem
                    key={notification.id}
                    notification={notification}
                    onClick={handleNotificationClick}
                    onDelete={removeNotification}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
