import React, { useState, useRef, useEffect } from 'react';
import { Typography, Button } from '@material-tailwind/react';
import { BellIcon } from '@heroicons/react/24/outline';
import { useNotificationStore } from '../../stores/notificationStore';
import { NotificationItem } from './NotificationItem';
import type { Notification } from '../../types';

export const NotificationBell: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const popoverRef = useRef<HTMLDivElement>(null);
  const { notifications, unreadCount, markAsRead, markAllAsRead } = useNotificationStore();

  // Close on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen]);

  const handleNotificationClick = (notification: Notification) => {
    if (!notification.is_read) {
      markAsRead(notification.id);
    }
  };

  return (
    <div className="relative" ref={popoverRef}>
      <button
        className="relative p-1 rounded-full hover:bg-gray-100 transition-colors"
        onClick={() => setIsOpen(!isOpen)}
      >
        <BellIcon className="h-5 w-5 text-gray-600" />
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 bg-red-500 text-white text-xs rounded-full h-4 w-4 flex items-center justify-center">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {isOpen && (
        <div className="absolute top-full right-0 mt-2 w-80 bg-white rounded-lg shadow-xl border z-50 max-h-96 overflow-hidden flex flex-col">
          <div className="flex items-center justify-between p-3 border-b">
            <Typography variant="small" className="font-semibold" color="blue-gray">
              알림
            </Typography>
            {unreadCount > 0 && (
              <Button
                variant="text"
                size="sm"
                className="text-xs p-1"
                onClick={markAllAsRead}
              >
                모두 읽음
              </Button>
            )}
          </div>
          <div className="overflow-auto flex-1">
            {notifications.length === 0 ? (
              <div className="p-6 text-center">
                <Typography variant="small" color="gray">
                  알림이 없습니다.
                </Typography>
              </div>
            ) : (
              notifications.slice(0, 20).map((notification) => (
                <NotificationItem
                  key={notification.id}
                  notification={notification}
                  onClick={handleNotificationClick}
                />
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
};
