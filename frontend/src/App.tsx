import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider } from '@material-tailwind/react';
import { MainLayout } from './components/layout';
import {
  LoginPage,
  MainPage,
  ProfilePage,
  CompanyPage,
  SchedulePage,
  AdminPage,
} from './pages';

const App: React.FC = () => {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <Routes>
          {/* 로그인 페이지 */}
          <Route path="/login" element={<LoginPage />} />

          {/* 인증 필요한 페이지 */}
          <Route element={<MainLayout />}>
            <Route path="/" element={<MainPage />} />
            <Route path="/profile" element={<ProfilePage />} />
            <Route path="/company" element={<CompanyPage />} />
            <Route path="/schedule" element={<SchedulePage />} />
            <Route path="/admin" element={<AdminPage />} />
          </Route>

          {/* 404 - 메인으로 리다이렉트 */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  );
};

export default App;
