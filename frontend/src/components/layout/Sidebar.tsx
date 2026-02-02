import React, { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import {
  Card,
  Typography,
  List,
  ListItem,
  ListItemPrefix,
  Button,
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
  ShieldCheckIcon,
} from '@heroicons/react/24/outline';
import { useAuthStore } from '../../stores/authStore';
import { useChatStore } from '../../stores/chatStore';
import { ChatHistoryPanel } from './ChatHistoryPanel';
import { ProfileDialog } from '../profile/ProfileDialog';

/** Routes that require authentication to access */
const AUTH_REQUIRED_PATHS = new Set(['/company', '/schedule', '/admin']);

const menuItems = [
  { path: '/', label: '채팅', icon: ChatBubbleLeftRightIcon },
  { path: '/company', label: '기업 정보', icon: BuildingOfficeIcon },
  { path: '/schedule', label: '일정 관리', icon: CalendarDaysIcon },
  { path: '/guide', label: '사용 설명서', icon: BookOpenIcon },
  { path: '/admin', label: '관리자', icon: ShieldCheckIcon, adminOnly: true },
];

export const Sidebar: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { isAuthenticated, logout, user } = useAuthStore();
  const { createSession } = useChatStore();
  const [isProfileOpen, setIsProfileOpen] = useState(false);

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
    <Card className="h-screen w-64 flex flex-col shadow-xl shadow-blue-gray-900/5 rounded-none">
      {/* Logo */}
      <div className="p-4 border-b">
        <Typography variant="h5" color="blue">
          Bizi
        </Typography>
        <Typography variant="small" color="gray" className="text-xs">
          통합 창업/경영 상담
        </Typography>
      </div>

      {/* New Chat Button */}
      <div className="px-3 pt-3">
        <Button
          fullWidth
          color="blue"
          className="flex items-center justify-center gap-2"
          size="sm"
          onClick={handleNewChat}
        >
          <PlusIcon className="h-4 w-4" />
          새 채팅
        </Button>
      </div>

      {/* Chat History */}
      <div className="flex-1 overflow-hidden flex flex-col mt-2">
        <ChatHistoryPanel />
      </div>

      {/* Divider */}
      <div className="border-t" />

      {/* Navigation Menu */}
      <div className="px-1">
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
                <Typography variant="small">{item.label}</Typography>
              </ListItem>
            </Link>
          ))}
        </List>
      </div>

      {/* Divider */}
      <div className="border-t" />

      {/* User Info + Settings / Login */}
      <div className="p-3">
        {isAuthenticated && user ? (
          <>
            <div className="flex items-center justify-between mb-2">
              <div className="min-w-0 flex-1">
                <Typography variant="small" color="blue-gray" className="font-medium truncate">
                  {user.username}
                </Typography>
                <Typography variant="small" color="gray" className="text-xs truncate">
                  {user.google_email}
                </Typography>
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
