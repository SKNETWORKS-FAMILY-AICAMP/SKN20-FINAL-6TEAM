import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  Card,
  Typography,
  List,
  ListItem,
  ListItemPrefix,
} from '@material-tailwind/react';
import {
  ChatBubbleLeftRightIcon,
  UserCircleIcon,
  BuildingOfficeIcon,
  CalendarDaysIcon,
  Cog6ToothIcon,
  ArrowLeftOnRectangleIcon,
} from '@heroicons/react/24/outline';
import { useAuthStore } from '../../stores/authStore';

const menuItems = [
  { path: '/', label: '채팅', icon: ChatBubbleLeftRightIcon },
  { path: '/profile', label: '프로필', icon: UserCircleIcon },
  { path: '/company', label: '기업 정보', icon: BuildingOfficeIcon },
  { path: '/schedule', label: '일정 관리', icon: CalendarDaysIcon },
  { path: '/admin', label: '관리자', icon: Cog6ToothIcon },
];

export const Sidebar: React.FC = () => {
  const location = useLocation();
  const { logout, user } = useAuthStore();

  const handleLogout = () => {
    logout();
    window.location.href = '/login';
  };

  return (
    <Card className="h-screen w-64 p-4 shadow-xl shadow-blue-gray-900/5 rounded-none">
      <div className="mb-4 p-4">
        <Typography variant="h5" color="blue-gray">
          BizMate
        </Typography>
        <Typography variant="small" color="gray" className="mt-1">
          통합 창업/경영 상담
        </Typography>
      </div>
      <List>
        {menuItems.map((item) => (
          <Link to={item.path} key={item.path}>
            <ListItem
              selected={location.pathname === item.path}
              className={location.pathname === item.path ? 'bg-blue-50' : ''}
            >
              <ListItemPrefix>
                <item.icon className="h-5 w-5" />
              </ListItemPrefix>
              {item.label}
            </ListItem>
          </Link>
        ))}
      </List>
      <div className="mt-auto border-t pt-4">
        {user && (
          <div className="px-4 py-2 mb-2">
            <Typography variant="small" color="gray">
              {user.username}
            </Typography>
            <Typography variant="small" color="gray" className="text-xs">
              {user.google_email}
            </Typography>
          </div>
        )}
        <ListItem onClick={handleLogout} className="text-red-500 hover:bg-red-50">
          <ListItemPrefix>
            <ArrowLeftOnRectangleIcon className="h-5 w-5" />
          </ListItemPrefix>
          로그아웃
        </ListItem>
      </div>
    </Card>
  );
};
