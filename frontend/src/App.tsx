import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider } from '@material-tailwind/react';
import { MainLayout } from './components/layout';
import {
  LoginPage,
  MainPage,
  CompanyPage,
  SchedulePage,
  AdminPage,
  UsageGuidePage,
} from './pages';

const App: React.FC = () => {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <Routes>
          {/* Login page */}
          <Route path="/login" element={<LoginPage />} />

          {/* All pages under MainLayout (authenticated + unauthenticated) */}
          <Route element={<MainLayout />}>
            <Route path="/" element={<MainPage />} />
            <Route path="/company" element={<CompanyPage />} />
            <Route path="/schedule" element={<SchedulePage />} />
            <Route path="/guide" element={<UsageGuidePage />} />
            <Route path="/admin" element={<AdminPage />} />
          </Route>

          {/* Catch-all redirect (including /guest) */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  );
};

export default App;
