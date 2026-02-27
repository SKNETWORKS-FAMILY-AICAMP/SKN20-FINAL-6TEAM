import React, { useEffect } from 'react';
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useLocation,
} from 'react-router-dom';
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

const LoginRedirect: React.FC = () => {
  useEffect(() => {
    useAuthStore.getState().openLoginModal();
  }, []);
  return <Navigate to="/" replace />;
};

const AppRoutes: React.FC = () => {
  const location = useLocation();
  const isLoginModalOpen = useAuthStore((s) => s.isLoginModalOpen);

  return (
    <>
      <Routes location={location}>
        <Route element={<MainLayout />}>
          <Route path="/" element={<MainPage />} />
          <Route path="/guide" element={<UsageGuidePage />} />

          <Route element={<ProtectedRoute />}>
            <Route path="/company" element={<CompanyPage />} />
            <Route path="/schedule" element={<SchedulePage />} />
          </Route>

          <Route element={<ProtectedRoute requiredTypeCode="U0000001" />}>
            <Route path="/admin" element={<AdminDashboardPage />} />
            <Route path="/admin/log" element={<AdminLogPage />} />
          </Route>
        </Route>

        <Route path="/login" element={<LoginRedirect />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>

      {isLoginModalOpen && <LoginPage />}
    </>
  );
};

const App: React.FC = () => {
  useEffect(() => {
    useAuthStore.getState().checkAuth();
  }, []);

  return (
    <ErrorBoundary>
      <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
        <ThemeProvider>
          <BrowserRouter>
            <AppRoutes />
          </BrowserRouter>
        </ThemeProvider>
      </GoogleOAuthProvider>
    </ErrorBoundary>
  );
};

export default App;
