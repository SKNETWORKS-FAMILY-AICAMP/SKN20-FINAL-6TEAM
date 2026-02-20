import React, { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import {
  Card,
  Typography,
  List,
  ListItem,
  ListItemPrefix,
  Button,
  IconButton,
  Tooltip,
  Chip,
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
} from '@heroicons/react/24/outline';
import { useAuthStore } from '../../stores/authStore';
import { useChatStore } from '../../stores/chatStore';
import { useDisplayUserType } from '../../hooks/useDisplayUserType';
import { USER_TYPE_NAMES } from '../../types';
import { ChatHistoryPanel } from './ChatHistoryPanel';
import { ProfileDialog } from '../profile/ProfileDialog';

/** Routes that require authentication to access */
const AUTH_REQUIRED_PATHS = new Set(['/company', '/schedule', '/admin', '/admin/log']);

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
}

export const Sidebar: React.FC<SidebarProps> = ({ collapsed, onToggle }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const { isAuthenticated, logout, user } = useAuthStore();
  const { createSession } = useChatStore();
  const displayUserType = useDisplayUserType();
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [isChatBtnHovered, setIsChatBtnHovered] = useState(false);
  const [isIconBtnHovered, setIsIconBtnHovered] = useState(false);

  const handleLogout = () => {
    logout();
    window.location.href = '/login';
  };

  const handleNewChat = () => {
    createSession();
    navigate('/');
  };

  const handleMenuClick = (e: React.MouseEvent, path: string) => {
    if (!isAuthenticated && AUTH_REQUIRED_PATHS.has(path)) {
      e.preventDefault();
      navigate('/login');
    }
  };

  const visibleMenuItems = menuItems.filter((item) => {
    if (item.adminOnly && user?.type_code !== 'U0000001') {
      return false;
    }
    return true;
  });

  return (
    <>
    <Card
      className={`h-screen flex flex-col shadow-xl shadow-blue-gray-900/5 rounded-none overflow-hidden transition-all duration-300 ease-in-out ${
        collapsed ? 'w-16' : 'w-64'
      }`}
    >
      {/* Logo / Toggle */}
      <div className={`px-4 border-b flex items-center justify-between ${
                      collapsed ? 'py-[13.5px] min-h-[40px]' : 'py-[18.5px] min-h-[55px]'
                      }`}>
        {collapsed ? (
          <div className="w-full flex flex-col items-center gap-1">
            <button
              onClick={() => navigate('/')}
              className="hover:opacity-80 transition-opacity"
              title="메인 페이지로 이동"
            >
              <Typography variant="h6" color="blue" className="font-bold">
                B
              </Typography>
            </button>
            <button
              onClick={onToggle}
              className="p-1 rounded hover:bg-gray-100 transition-colors"
              title="사이드바 펼치기"
            >
              <ChevronRightIcon className="h-4 w-4 text-gray-600" />
            </button>
          </div>
        ) : (
          <>
            <button
              onClick={() => navigate('/')}
              className="hover:opacity-80 transition-opacity text-left"
              title="메인 페이지로 이동"
            >
              <Typography variant="h5" color="blue">
                Bizi
              </Typography>
              <Typography variant="small" color="gray" className="text-xs !text-gray-600">
                통합 창업/경영 상담
              </Typography>
            </button>
            <button
              onClick={onToggle}
              className="p-1 rounded hover:bg-gray-100 transition-colors"
              title="사이드바 접기"
            >
              <ChevronLeftIcon className="h-5 w-5 text-gray-600" />
            </button>
          </>
        )}
      </div>

      {/* New Chat Button */}
      <div className="px-3 pt-[10px]">
        {collapsed ? (
          <Tooltip content="새 채팅" placement="right">
            <IconButton
              color="blue"
              size="sm"
              className={`w-full !shadow-none transition-all duration-150 ${
                isIconBtnHovered ? '!bg-blue-900' : '!border-transparent'
              }`}
              onClick={handleNewChat}
              onMouseEnter={() => setIsIconBtnHovered(true)}
              onMouseLeave={() => setIsIconBtnHovered(false)}
            >
              <PlusIcon className="h-4 w-4" />
            </IconButton>
          </Tooltip>
        ) : (
          <Button
            fullWidth
            color="blue"
            className={`flex items-center justify-center gap-2 !shadow-none transition-all duration-150 ${
              isChatBtnHovered ? '!bg-blue-900' : '!border-transparent'
            }`}
            size="sm"
            onClick={handleNewChat}
            onMouseEnter={() => setIsChatBtnHovered(true)}
            onMouseLeave={() => setIsChatBtnHovered(false)}
          >
            <PlusIcon className="h-4 w-4" />
            새 채팅
          </Button>
        )}
      </div>

      {/* Chat History */}
      <div className="flex-1 overflow-hidden flex flex-col mt-2">
        <ChatHistoryPanel collapsed={collapsed} />
      </div>

      {/* Divider */}
      <div className="border-t" />

      {/* Navigation Menu */}
      <div className={collapsed ? 'px-1 py-1' : 'px-1'}>
        {collapsed ? (
          <div className="flex flex-col items-center gap-1">
            {visibleMenuItems.map((item) => (
              <Tooltip key={item.path} content={item.label} placement="right">
                <Link
                  to={item.path}
                  onClick={(e) => handleMenuClick(e, item.path)}
                >
                  <IconButton
                    variant="text"
                    color={location.pathname === item.path ? 'blue' : 'blue-gray'}
                    size="sm"
                    className={location.pathname === item.path ? 'bg-blue-50' : ''}
                  >
                    <item.icon className="h-5 w-5" />
                  </IconButton>
                </Link>
              </Tooltip>
            ))}
          </div>
        ) : (
          <List className="min-w-0 p-1">
            {visibleMenuItems.map((item) => (
              <Link
                to={item.path}
                key={item.path}
                onClick={(e) => handleMenuClick(e, item.path)}
              >
                <ListItem
                  selected={location.pathname === item.path}
                  className={`py-2 ${location.pathname === item.path ? 'bg-blue-50' : ''}`}
                >
                  <ListItemPrefix>
                    <item.icon className="h-5 w-5" />
                  </ListItemPrefix>
                  <Typography variant="small" className="!text-gray-800">{item.label}</Typography>
                </ListItem>
              </Link>
            ))}
          </List>
        )}
      </div>

      {/* Divider */}
      <div className="border-t" />

      {/* User Info + Settings / Login */}
      <div className={collapsed ? 'p-2' : 'p-3'}>
        {isAuthenticated && user ? (
          collapsed ? (
            <div className="flex flex-col items-center gap-1">
              <Tooltip content="설정" placement="right">
                <button
                  className="p-1 rounded-full hover:bg-gray-100 transition-colors"
                  onClick={() => setIsProfileOpen(true)}
                >
                  <Cog6ToothIcon className="h-5 w-5 text-gray-600" />
                </button>
              </Tooltip>
              <Tooltip content="로그아웃" placement="right">
                <button
                  className="p-1 rounded-full hover:bg-red-50 transition-colors"
                  onClick={handleLogout}
                >
                  <ArrowLeftOnRectangleIcon className="h-5 w-5 text-red-500" />
                </button>
              </Tooltip>
            </div>
          ) : (
            <>
              <div className="flex items-center justify-between mb-2">
                <div className="min-w-0 flex-1">
                  <Typography variant="small" color="blue-gray" className="font-medium truncate !text-gray-900">
                    {user.username}
                  </Typography>
                  <Typography variant="small" color="gray" className="text-xs truncate !text-gray-700">
                    {user.google_email}
                  </Typography>
                  <Chip
                    value={USER_TYPE_NAMES[displayUserType] || displayUserType}
                    color="blue"
                    variant="ghost"
                    size="sm"
                    className="mt-1"
                  />
                </div>
                <button
                  className="p-1 rounded-full hover:bg-gray-100 transition-colors"
                  onClick={() => setIsProfileOpen(true)}
                  title="설정"
                >
                  <Cog6ToothIcon className="h-5 w-5 text-gray-600" />
                </button>
              </div>
              <ListItem
                onClick={handleLogout}
                className="text-red-500 hover:bg-red-50 py-2"
              >
                <ListItemPrefix>
                  <ArrowLeftOnRectangleIcon className="h-5 w-5" />
                </ListItemPrefix>
                <Typography variant="small">로그아웃</Typography>
              </ListItem>
            </>
          )
        ) : collapsed ? (
          <div className="flex flex-col items-center">
            <Tooltip content="로그인" placement="right">
              <button
                className="p-1 rounded-full hover:bg-blue-50 transition-colors"
                onClick={() => navigate('/login')}
              >
                <ArrowRightOnRectangleIcon className="h-5 w-5 text-blue-500" />
              </button>
            </Tooltip>
          </div>
        ) : (
          <ListItem
            onClick={() => navigate('/login')}
            className="text-blue-500 hover:bg-blue-50 py-2"
          >
            <ListItemPrefix>
              <ArrowRightOnRectangleIcon className="h-5 w-5" />
            </ListItemPrefix>
            <Typography variant="small">로그인</Typography>
          </ListItem>
        )}
      </div>
    </Card>

      {/* Profile Dialog */}
      <ProfileDialog open={isProfileOpen} onClose={() => setIsProfileOpen(false)} />
    </>
  );
};
