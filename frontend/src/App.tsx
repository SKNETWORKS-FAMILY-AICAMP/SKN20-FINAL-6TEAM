import React, { useEffect } from 'react';
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useLocation,
  type Location,
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
const LOGIN_MODAL_BACKGROUND_LOCATION: Location = {
  pathname: '/',
  search: '',
  hash: '',
  state: null,
  key: 'login-modal-background',
};

interface LoginRouteState {
  backgroundLocation?: Location;
}

const AppRoutes: React.FC = () => {
  const location = useLocation();
  const state = location.state as LoginRouteState | null;
  const isLoginModalRoute = location.pathname === '/login';
  const backgroundLocation =
    state?.backgroundLocation ?? (isLoginModalRoute ? LOGIN_MODAL_BACKGROUND_LOCATION : undefined);

  return (
    <>
      <Routes location={backgroundLocation ?? location}>
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

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>

      {isLoginModalRoute && (
        <Routes>
          <Route path="/login" element={<LoginPage />} />
        </Routes>
      )}
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
