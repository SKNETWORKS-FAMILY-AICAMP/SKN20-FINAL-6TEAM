import React from 'react';
import { Navigate, Outlet, type Location, useLocation } from 'react-router-dom';
import { useAuthStore } from '../../stores/authStore';

interface ProtectedRouteProps {
  requiredTypeCode?: string;
}

const LOGIN_FALLBACK_BACKGROUND: Location = {
  pathname: '/',
  search: '',
  hash: '',
  state: null,
  key: 'protected-login-fallback',
};

const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ requiredTypeCode }) => {
  const location = useLocation();
  const { isAuthenticated, isAuthChecking, user } = useAuthStore();

  if (isAuthChecking) {
    return null;
  }

  if (!isAuthenticated) {
    return (
      <Navigate
        to="/login"
        replace
        state={{ backgroundLocation: location.pathname === '/login' ? LOGIN_FALLBACK_BACKGROUND : location }}
      />
    );
  }

  if (requiredTypeCode && user?.type_code !== requiredTypeCode) {
    return <Navigate to="/" replace />;
  }

  return <Outlet />;
};

export default ProtectedRoute;
