import React, { useEffect, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { IconButton } from '@material-tailwind/react';
import { Bars3Icon } from '@heroicons/react/24/outline';
import { Sidebar } from './Sidebar';
import { NotificationToast } from './NotificationToast';
import { ToastContainer } from '../common/ToastContainer';
import { useMediaQuery } from '../../hooks/useMediaQuery';
import { useAuthStore } from '../../stores/authStore';
import { useNotificationStore } from '../../stores/notificationStore';

const SIDEBAR_COLLAPSED_STORAGE_KEY = 'bizi.sidebar.collapsed.desktop';
const MOBILE_BREAKPOINT_QUERY = '(max-width: 1023px)';
const MAX_VISIBLE_TOASTS = 5;

const getInitialDesktopCollapseState = (): boolean => {
  if (typeof window === 'undefined') {
    return false;
  }

  return window.localStorage.getItem(SIDEBAR_COLLAPSED_STORAGE_KEY) === '1';
};

export const MainLayout: React.FC = () => {
  const location = useLocation();
  const isMobile = useMediaQuery(MOBILE_BREAKPOINT_QUERY);
  const { isAuthenticated } = useAuthStore();
  const { notifications, toastQueue, dismissToast } = useNotificationStore();
  const [isSidebarCollapsedDesktop, setIsSidebarCollapsedDesktop] = useState<boolean>(
    getInitialDesktopCollapseState
  );
  const [isSidebarOpenMobile, setIsSidebarOpenMobile] = useState(false);
  const visibleToastNotifications = toastQueue
    .slice(0, MAX_VISIBLE_TOASTS)
    .map((toastId) => notifications.find((notification) => notification.id === toastId) ?? null)
    .filter((notification): notification is NonNullable<typeof notification> => notification !== null);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    window.localStorage.setItem(
      SIDEBAR_COLLAPSED_STORAGE_KEY,
      isSidebarCollapsedDesktop ? '1' : '0'
    );
  }, [isSidebarCollapsedDesktop]);

  useEffect(() => {
    setIsSidebarOpenMobile(false);
  }, [location.pathname, location.search]);

  useEffect(() => {
    if (!isMobile) {
      document.body.style.overflow = '';
      return;
    }

    document.body.style.overflow = isSidebarOpenMobile ? 'hidden' : '';

    return () => {
      document.body.style.overflow = '';
    };
  }, [isMobile, isSidebarOpenMobile]);

  return (
    <div className="flex h-[100dvh] min-h-0 bg-gray-50">
      <Sidebar
        collapsed={isMobile ? false : isSidebarCollapsedDesktop}
        onToggle={() => setIsSidebarCollapsedDesktop((prev) => !prev)}
        isMobile={isMobile}
        isOpen={isMobile ? isSidebarOpenMobile : true}
        onClose={() => setIsSidebarOpenMobile(false)}
      />
      <main className="relative flex-1 min-h-0 min-w-0 overflow-auto">
        {isAuthenticated &&
          visibleToastNotifications.map((notification, index) => (
            <NotificationToast
              key={notification.id}
              notification={notification}
              onClose={() => dismissToast(notification.id)}
              placement="bell-side"
              stackIndex={index}
            />
          ))}
        {isMobile && !isSidebarOpenMobile && (
          <div className="pointer-events-none fixed left-3 top-3 z-30 lg:hidden">
            <div className="pointer-events-auto rounded-xl border border-gray-200 bg-white/95 p-1 shadow-lg backdrop-blur">
              <IconButton
                variant="text"
                size="sm"
                className="h-9 w-9 min-w-0 rounded-lg text-gray-700"
                onClick={() => setIsSidebarOpenMobile(true)}
                aria-label="사이드바 열기"
                aria-controls="app-sidebar"
                aria-expanded={isSidebarOpenMobile}
              >
                <Bars3Icon className="h-5 w-5" />
              </IconButton>
            </div>
          </div>
        )}
        <Outlet />
        <ToastContainer />
      </main>
    </div>
  );
};
