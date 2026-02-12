import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Card,
  CardBody,
  Typography,
  Button,
  Spinner,
} from '@material-tailwind/react';
import { ShieldCheckIcon } from '@heroicons/react/24/outline';
import { GoogleLogin, CredentialResponse } from '@react-oauth/google';
import { useAuthStore } from '../stores/authStore';
import api from '../lib/api';

const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const { login } = useAuthStore();
  const [error, setError] = useState<string | null>(null);
  const [adminLoading, setAdminLoading] = useState(false);

  const handleGoogleSuccess = async (credentialResponse: CredentialResponse) => {
    setError(null);

    try {
      const response = await api.post('/auth/google', {
        id_token: credentialResponse.credential,
      });
      const { user } = response.data;

      login(user);
      navigate('/');
    } catch (err: unknown) {
      console.error('Login error:', err);
      const error = err as { response?: { data?: { detail?: string } } };
      setError(error.response?.data?.detail || '로그인에 실패했습니다.');
    }
  };

  const handleGoogleError = () => {
    setError('Google 로그인에 실패했습니다. 다시 시도해주세요.');
  };

  const handleAdminLogin = async () => {
    setError(null);
    setAdminLoading(true);
    try {
      const response = await api.post('/auth/test-login', {
        email: 'admin@bizi.com',
        username: '관리자',
        type_code: 'U0000001',
      });
      const { user } = response.data;
      login(user);
      navigate('/admin');
    } catch (err: unknown) {
      console.error('Admin login error:', err);
      const error = err as { response?: { data?: { detail?: string } } };
      setError(error.response?.data?.detail || '관리자 로그인에 실패했습니다.');
    } finally {
      setAdminLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-blue-100">
      <Card className="w-full max-w-md">
        <CardBody className="flex flex-col gap-6 p-8">
          {/* 로고 및 타이틀 */}
          <div className="text-center">
            <Typography variant="h3" color="blue-gray" className="mb-2">
              Bizi
            </Typography>
            <Typography variant="paragraph" color="gray">
              통합 창업/경영 상담 챗봇
            </Typography>
          </div>

          {/* 설명 */}
          <div className="bg-blue-50 p-4 rounded-lg">
            <Typography variant="small" color="blue-gray">
              Bizi는 예비 창업자, 스타트업 CEO, 중소기업 대표를 위한
              AI 기반 통합 경영 상담 서비스입니다.
            </Typography>
            <ul className="mt-3 space-y-1 text-sm text-gray-600">
              <li>창업 절차 및 사업자 등록 안내</li>
              <li>세무/회계 상담</li>
              <li>인사/노무 관련 상담</li>
              <li>법률 자문</li>
              <li>정부 지원사업 매칭</li>
              <li>마케팅 전략 상담</li>
            </ul>
          </div>

          {/* 에러 메시지 */}
          {error && (
            <div className="bg-red-50 text-red-500 p-3 rounded-lg text-sm">
              {error}
            </div>
          )}

          {/* Google 로그인 버튼 */}
          <div className="flex justify-center">
            <GoogleLogin
              onSuccess={handleGoogleSuccess}
              onError={handleGoogleError}
              size="large"
              width="350"
              text="signin_with"
              shape="rectangular"
            />
          </div>

          {/* 구분선 */}
          <div className="flex items-center gap-3">
            <div className="flex-1 border-t border-gray-300" />
            <Typography variant="small" color="gray">
              또는
            </Typography>
            <div className="flex-1 border-t border-gray-300" />
          </div>

          {/* 관리자 로그인 버튼 */}
          <Button
            variant="outlined"
            color="blue-gray"
            fullWidth
            className="flex items-center justify-center gap-2"
            onClick={handleAdminLogin}
            disabled={adminLoading}
          >
            {adminLoading ? (
              <Spinner className="h-4 w-4" />
            ) : (
              <ShieldCheckIcon className="h-5 w-5" />
            )}
            관리자 로그인
          </Button>
        </CardBody>
      </Card>
    </div>
  );
};

export default LoginPage;
