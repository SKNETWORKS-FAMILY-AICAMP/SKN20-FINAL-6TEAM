import React, { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider } from '@material-tailwind/react';
import { GoogleOAuthProvider } from '@react-oauth/google';
import { MainLayout } from './components/layout';
import ProtectedRoute from './components/common/ProtectedRoute';
import ErrorBoundary from './components/common/ErrorBoundary';
import {
  LoginPage,
  MainPage,
  CompanyPage,
  SchedulePage,
  AdminDashboardPage,
  AdminLogPage,
  UsageGuidePage,
} from './pages';
import { useAuthStore } from './stores/authStore';

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || '';

const App: React.FC = () => {
  useEffect(() => {
    useAuthStore.getState().checkAuth();
  }, []);

  return (
    <ErrorBoundary>
    <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
      <ThemeProvider>
        <BrowserRouter>
          <Routes>
            {/* Login page */}
            <Route path="/login" element={<LoginPage />} />

            {/* All pages under MainLayout */}
            <Route element={<MainLayout />}>
              {/* 게스트 허용 */}
              <Route path="/" element={<MainPage />} />
              <Route path="/guide" element={<UsageGuidePage />} />

              {/* 인증 필요 */}
              <Route element={<ProtectedRoute />}>
                <Route path="/company" element={<CompanyPage />} />
                <Route path="/schedule" element={<SchedulePage />} />
              </Route>

              {/* 관리자 전용 */}
              <Route element={<ProtectedRoute requiredTypeCode="U0000001" />}>
                <Route path="/admin" element={<AdminDashboardPage />} />
                <Route path="/admin/log" element={<AdminLogPage />} />
              </Route>
            </Route>

            {/* Catch-all redirect */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </ThemeProvider>
    </GoogleOAuthProvider>
    </ErrorBoundary>
  );
};

export default App;
