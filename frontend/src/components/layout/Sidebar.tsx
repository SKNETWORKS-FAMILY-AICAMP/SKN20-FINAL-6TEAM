import React, { useEffect, useRef, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import {
  Card,
  Typography,
  Tooltip,
} from '@material-tailwind/react';
import {
  ChatBubbleLeftRightIcon,
  BuildingOfficeIcon,
  CalendarDaysIcon,
  Cog6ToothIcon,
  ArrowLeftOnRectangleIcon,
  ArrowRightOnRectangleIcon,
  PlusIcon,
  BookOpenIcon,
  ChartBarIcon,
  ClipboardDocumentListIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  UserCircleIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';
import { useAuthStore } from '../../stores/authStore';
import { useChatStore } from '../../stores/chatStore';
import { useDisplayUserType } from '../../hooks/useDisplayUserType';
import { USER_TYPE_NAMES } from '../../types';
import { ChatHistoryPanel } from './ChatHistoryPanel';
import { ProfileDialog } from '../profile/ProfileDialog';

/** Routes that require authentication to access */
const AUTH_REQUIRED_PATHS = new Set(['/company', '/schedule', '/admin', '/admin/log']);
const MOBILE_SIDEBAR_WIDTH_CLASS = 'w-[min(85vw,20rem)]';
const DESKTOP_SIDEBAR_EXPANDED_WIDTH_CLASS = 'w-64';
const DESKTOP_SIDEBAR_COLLAPSED_WIDTH_CLASS = 'w-16';
const SIDEBAR_WIDTH_TRANSITION_CLASS = 'transition-[width] duration-180 ease-[cubic-bezier(0.2,0,0,1)]';
const LABEL_TRANSITION_CLASS =
  'transition-[max-width,opacity] duration-120 ease-[cubic-bezier(0.2,0,0,1)]';

const menuItems = [
  { path: '/', label: '채팅', icon: ChatBubbleLeftRightIcon },
  { path: '/company', label: '기업 정보', icon: BuildingOfficeIcon },
  { path: '/schedule', label: '일정 관리', icon: CalendarDaysIcon },
  { path: '/guide', label: '사용 설명서', icon: BookOpenIcon },
  { path: '/admin', label: '대시보드', icon: ChartBarIcon, adminOnly: true },
  { path: '/admin/log', label: '상담 로그', icon: ClipboardDocumentListIcon, adminOnly: true },
];

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
  isMobile?: boolean;
  isOpen?: boolean;
  onClose?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  collapsed,
  onToggle,
  isMobile = false,
  isOpen = true,
  onClose,
}) => {
  const location = useLocation();
  const navigate = useNavigate();
  const { isAuthenticated, logout, user } = useAuthStore();
  const { createSession } = useChatStore();
  const displayUserType = useDisplayUserType();
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const effectiveCollapsed = isMobile ? false : collapsed;

  const closeSidebar = () => {
    if (isMobile) {
      onClose?.();
    }
  };

  useEffect(() => {
    if (!isMobile || !isOpen) {
      return;
    }

    closeButtonRef.current?.focus();
  }, [isMobile, isOpen]);

  useEffect(() => {
    if (!isMobile || !isOpen) {
      return;
    }

    const handleKeydown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose?.();
      }
    };

    window.addEventListener('keydown', handleKeydown);
    return () => {
      window.removeEventListener('keydown', handleKeydown);
    };
  }, [isMobile, isOpen, onClose]);

  const handleLogout = async () => {
    closeSidebar();
    await logout();
    navigate('/', { replace: true });
  };

  const handleNewChat = () => {
    createSession();
    navigate('/');
    closeSidebar();
  };

  const handleMenuClick = (event: React.MouseEvent<HTMLAnchorElement>, path: string) => {
    if (!isAuthenticated && AUTH_REQUIRED_PATHS.has(path)) {
      event.preventDefault();
      navigate('/login', { state: { backgroundLocation: location } });
    }

    closeSidebar();
  };

  const handleProfileOpen = () => {
    setIsProfileOpen(true);
    closeSidebar();
  };

  const visibleMenuItems = menuItems.filter((item) => {
    if (item.adminOnly && user?.type_code !== 'U0000001') {
      return false;
    }
    return true;
  });

  return (
    <>
      {isMobile && (
        <div
          className={`fixed inset-0 z-40 bg-black/35 transition-opacity duration-200 ${
            isOpen ? 'opacity-100' : 'pointer-events-none opacity-0'
          }`}
          onClick={onClose}
          aria-hidden
        />
      )}

      <aside
        id="app-sidebar"
        className={
          isMobile
            ? `fixed inset-y-0 left-0 z-50 transform transition-transform duration-300 ease-out ${
                isOpen ? 'translate-x-0' : '-translate-x-full'
              }`
            : 'relative h-full shrink-0 border-r border-gray-200 bg-white'
        }
        role={isMobile ? 'dialog' : undefined}
        aria-modal={isMobile ? true : undefined}
        aria-label="사이드바"
      >
        <Card
          shadow={false}
          style={{ boxShadow: 'none' }}
          className={`flex flex-col overflow-hidden rounded-none bg-white shadow-none ${
            isMobile
              ? `h-full ${MOBILE_SIDEBAR_WIDTH_CLASS}`
              : `h-full ${effectiveCollapsed ? DESKTOP_SIDEBAR_COLLAPSED_WIDTH_CLASS : DESKTOP_SIDEBAR_EXPANDED_WIDTH_CLASS} ${SIDEBAR_WIDTH_TRANSITION_CLASS}`
          }`}
        >
          {/* Logo / Toggle */}
          <div className="flex h-[81px] items-center border-b px-3">
            <div
              className={`min-w-0 overflow-hidden transition-[max-width] duration-180 ease-[cubic-bezier(0.2,0,0,1)] ${
                !isMobile && effectiveCollapsed ? 'max-w-0 flex-1' : 'max-w-[13rem] flex-1'
              }`}
            >
              <button
                onClick={() => navigate('/')}
                className={`min-w-0 overflow-hidden text-left transition-[transform,opacity] duration-140 ease-[cubic-bezier(0.2,0,0,1)] hover:opacity-80 ${
                  effectiveCollapsed ? '-translate-x-1 opacity-0 pointer-events-none' : 'translate-x-0 opacity-100'
                }`}
                title="메인 페이지로 이동"
              >
                <Typography variant="h5" color="blue">
                  Bizi
                </Typography>
                <Typography variant="small" color="gray" className="text-xs !text-gray-600">
                  통합 창업/경영 상담
                </Typography>
              </button>
            </div>

            {isMobile ? (
              <button
                ref={closeButtonRef}
                onClick={onClose}
                className="ml-auto rounded p-1 transition-colors hover:bg-gray-100"
                title="사이드바 닫기"
                aria-label="사이드바 닫기"
              >
                <XMarkIcon className="h-5 w-5 text-gray-600" />
              </button>
            ) : (
              <button
                onClick={onToggle}
                className="ml-auto flex h-10 w-10 items-center justify-center rounded-lg transition-colors hover:bg-gray-100"
                title={effectiveCollapsed ? '사이드바 펼치기' : '사이드바 접기'}
              >
                {effectiveCollapsed ? (
                  <ChevronRightIcon className="h-5 w-5 text-gray-600" />
                ) : (
                  <ChevronLeftIcon className="h-5 w-5 text-gray-600" />
                )}
              </button>
            )}
          </div>

          {/* New Chat Button */}
          <div className="px-2 pt-2">
            <button
              type="button"
              className="flex h-10 w-full items-center justify-start gap-0 overflow-hidden rounded-lg bg-blue-500 px-2 text-sm font-medium text-white transition-colors duration-150 hover:bg-blue-600"
              onClick={handleNewChat}
              title={effectiveCollapsed ? '새 채팅' : undefined}
            >
              <span className="flex h-10 w-10 items-center justify-center">
                <PlusIcon className="h-5 w-5 flex-shrink-0" />
              </span>
              <span
                className={`inline-block overflow-hidden whitespace-nowrap ${LABEL_TRANSITION_CLASS} ${
                  effectiveCollapsed ? 'max-w-0 opacity-0' : 'max-w-[6rem] opacity-100'
                }`}
              >
                새 채팅
              </span>
            </button>
          </div>

          {/* Chat History */}
          <div className="mt-2 flex flex-1 flex-col overflow-hidden">
            <ChatHistoryPanel
              collapsed={effectiveCollapsed}
              mobile={isMobile}
              onSelectSession={closeSidebar}
            />
          </div>

          {/* Divider */}
          <div className="border-t" />

          {/* Navigation Menu */}
          <div className="space-y-1 px-2 py-1">
            {visibleMenuItems.map((item) => (
              <Link
                to={item.path}
                key={item.path}
                onClick={(event) => handleMenuClick(event, item.path)}
                title={effectiveCollapsed ? item.label : undefined}
                className={`flex h-10 items-center rounded-lg transition-colors duration-150 ${
                  location.pathname === item.path ? 'bg-blue-50 text-blue-700' : 'text-gray-700 hover:bg-gray-100'
                } w-full justify-start px-2`}
              >
                <span className="flex h-10 w-10 items-center justify-center">
                  <item.icon className="h-5 w-5" />
                </span>
                <Typography
                  variant="small"
                  className={`overflow-hidden whitespace-nowrap !text-gray-800 ${LABEL_TRANSITION_CLASS} ${
                    effectiveCollapsed ? 'max-w-0 opacity-0' : 'max-w-[9rem] opacity-100'
                  }`}
                >
                  {item.label}
                </Typography>
              </Link>
            ))}
          </div>

          {/* Divider */}
          <div className="border-t" />

          {/* User Info + Settings / Login */}
          <div className="p-2">
            {isAuthenticated && user ? (
              effectiveCollapsed ? (
                <div className="flex flex-col items-center gap-1">
                  <Tooltip content="설정" placement="right">
                    <button
                      className="flex h-10 w-10 items-center justify-center rounded-lg transition-colors hover:bg-gray-100"
                      onClick={handleProfileOpen}
                    >
                      <Cog6ToothIcon className="h-5 w-5 text-gray-600" />
                    </button>
                  </Tooltip>
                  <Tooltip content="로그아웃" placement="right">
                    <button
                      className="flex h-10 w-10 items-center justify-center rounded-lg transition-colors hover:bg-red-50"
                      onClick={handleLogout}
                    >
                      <ArrowLeftOnRectangleIcon className="h-5 w-5 text-red-500" />
                    </button>
                  </Tooltip>
                </div>
              ) : (
                <>
                  <div className="mb-1 flex items-center rounded-lg px-2">
                    <span className="flex h-10 w-10 items-center justify-center">
                      <UserCircleIcon className="h-5 w-5 text-gray-500" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <Typography
                        variant="small"
                        color="blue-gray"
                        className="truncate font-medium !text-gray-900"
                      >
                        {user.username}
                      </Typography>
                      <Typography
                        variant="small"
                        className="mt-1 inline-flex max-w-full items-center rounded-md bg-blue-50 px-2 py-0.5 text-xs !text-blue-700"
                      >
                        {USER_TYPE_NAMES[displayUserType] || displayUserType}
                      </Typography>
                    </div>
                    <button
                      type="button"
                      className="ml-1 flex h-10 w-10 items-center justify-center rounded-lg transition-colors hover:bg-gray-100"
                      onClick={handleProfileOpen}
                      title="설정"
                    >
                      <Cog6ToothIcon className="h-5 w-5 text-gray-600" />
                    </button>
                  </div>
                  <button
                    type="button"
                    onClick={handleLogout}
                    className="flex h-10 w-full items-center justify-start gap-0 rounded-lg px-2 text-red-500 transition-colors duration-150 hover:bg-red-50"
                  >
                    <span className="flex h-10 w-10 items-center justify-center">
                      <ArrowLeftOnRectangleIcon className="h-5 w-5" />
                    </span>
                    <Typography variant="small">로그아웃</Typography>
                  </button>
                </>
              )
            ) : (
              <button
                type="button"
                onClick={() => {
                  navigate('/login', { state: { backgroundLocation: location } });
                  closeSidebar();
                }}
                title={effectiveCollapsed ? '로그인' : undefined}
                className="flex h-10 w-full items-center justify-start gap-0 overflow-hidden rounded-lg px-2 text-blue-500 transition-colors duration-150 hover:bg-blue-50"
              >
                <span className="flex h-10 w-10 items-center justify-center">
                  <ArrowRightOnRectangleIcon className="h-5 w-5 flex-shrink-0" />
                </span>
                <Typography
                  variant="small"
                  className={`overflow-hidden whitespace-nowrap ${LABEL_TRANSITION_CLASS} ${
                    effectiveCollapsed ? 'max-w-0 opacity-0' : 'max-w-[6rem] opacity-100'
                  }`}
                >
                  로그인
                </Typography>
              </button>
            )}
          </div>
        </Card>
      </aside>

      {/* Profile Dialog */}
      <ProfileDialog open={isProfileOpen} onClose={() => setIsProfileOpen(false)} />
    </>
  );
};
