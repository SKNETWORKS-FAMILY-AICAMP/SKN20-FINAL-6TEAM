import React, { useEffect } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuthStore } from '../../stores/authStore';

interface ProtectedRouteProps {
  requiredTypeCode?: string;
}

const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ requiredTypeCode }) => {
  const { isAuthenticated, isAuthChecking, user, openLoginModal } = useAuthStore();

  useEffect(() => {
    if (!isAuthChecking && !isAuthenticated) {
      openLoginModal();
    }
  }, [isAuthChecking, isAuthenticated, openLoginModal]);

  if (isAuthChecking || !isAuthenticated) {
    return null;
  }

  if (requiredTypeCode && user?.type_code !== requiredTypeCode) {
    return <Navigate to="/" replace />;
  }

  return <Outlet />;
};

export default ProtectedRoute;
