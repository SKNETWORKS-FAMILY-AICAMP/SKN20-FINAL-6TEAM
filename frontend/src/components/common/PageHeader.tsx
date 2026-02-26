import React from 'react';
import { Typography } from '@material-tailwind/react';
import { NotificationBell } from '../layout/NotificationBell';
import { useAuthStore } from '../../stores/authStore';

interface PageHeaderProps {
  title: React.ReactNode;
  description?: React.ReactNode;
  rightSlot?: React.ReactNode;
  className?: string;
  contentClassName?: string;
  mobileNotificationOnTop?: boolean;
}

export const PageHeader: React.FC<PageHeaderProps> = ({
  title,
  description,
  rightSlot,
  className = '',
  contentClassName = '',
  mobileNotificationOnTop = false,
}) => {
  const { isAuthenticated } = useAuthStore();
  const hasActions = Boolean(rightSlot) || isAuthenticated;

  return (
    <div className={`border-b bg-white p-4 ${className}`.trim()}>
      {mobileNotificationOnTop ? (
        <div className={`flex flex-wrap items-start justify-between gap-2 ${contentClassName}`.trim()}>
          <div className="min-w-0 pl-12 lg:pl-0">
            <Typography variant="h5" color="blue-gray" className="!text-gray-900">
              {title}
            </Typography>
            <Typography
              variant="small"
              color="gray"
              className={description ? '!text-gray-700' : 'invisible'}
              aria-hidden={description ? undefined : true}
            >
              {description ?? '\u00A0'}
            </Typography>
          </div>

          {isAuthenticated ? (
            <div className="flex shrink-0 items-center justify-end">
              <NotificationBell />
            </div>
          ) : null}

          {rightSlot ? <div className="w-full lg:w-auto">{rightSlot}</div> : null}
        </div>
      ) : (
        <div className={`flex items-center justify-between gap-3 ${contentClassName}`.trim()}>
          <div className="min-w-0 pl-12 lg:pl-0">
            <Typography variant="h5" color="blue-gray" className="!text-gray-900">
              {title}
            </Typography>
            <Typography
              variant="small"
              color="gray"
              className={description ? '!text-gray-700' : 'invisible'}
              aria-hidden={description ? undefined : true}
            >
              {description ?? '\u00A0'}
            </Typography>
          </div>

          {hasActions ? (
            <div className="flex w-full flex-wrap items-center justify-end gap-2 lg:w-auto lg:flex-nowrap lg:gap-3">
              {rightSlot}
              {isAuthenticated ? <NotificationBell /> : null}
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
};

export default PageHeader;
