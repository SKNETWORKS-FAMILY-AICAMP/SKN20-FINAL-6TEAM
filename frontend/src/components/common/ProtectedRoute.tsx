import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { useAuthStore } from '../../stores/authStore';

interface ProtectedRouteProps {
  requiredTypeCode?: string;
}

const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ requiredTypeCode }) => {
  const { isAuthenticated, isAuthChecking, user } = useAuthStore();

  if (isAuthChecking) {
    return null;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (requiredTypeCode && user?.type_code !== requiredTypeCode) {
    return <Navigate to="/" replace />;
  }

  return <Outlet />;
};

export default ProtectedRoute;
