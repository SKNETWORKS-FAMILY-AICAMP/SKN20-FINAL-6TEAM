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
}

export const PageHeader: React.FC<PageHeaderProps> = ({
  title,
  description,
  rightSlot,
  className = '',
  contentClassName = '',
}) => {
  const { isAuthenticated } = useAuthStore();
  const hasActions = Boolean(rightSlot) || isAuthenticated;

  return (
    <div className={`border-b bg-white p-4 ${className}`.trim()}>
      <div className={`flex items-center justify-between gap-3 ${contentClassName}`.trim()}>
        <div className="min-w-0">
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
          <div className="flex shrink-0 items-center gap-3">
            {rightSlot}
            {isAuthenticated ? <NotificationBell /> : null}
          </div>
        ) : null}
      </div>
    </div>
  );
};

export default PageHeader;
