import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Card,
  CardBody,
  Typography,
  Button,
  Spinner,
} from '@material-tailwind/react';
import { useAuthStore } from '../stores/authStore';
import api from '../lib/api';

const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const { login } = useAuthStore();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleGoogleLogin = async () => {
    setIsLoading(true);
    setError(null);

    try {
      // 테스트 로그인 API 호출 (실제 Google 로그인 대신)
      const response = await api.post('/auth/test-login');
      const { access_token, user } = response.data;

      // 로그인 상태 저장
      login(user, access_token);

      // 메인 페이지로 이동
      navigate('/');
    } catch (err: any) {
      console.error('Login error:', err);
      setError(err.response?.data?.detail || '로그인에 실패했습니다.');
    } finally {
      setIsLoading(false);
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
          <Button
            size="lg"
            variant="outlined"
            color="blue-gray"
            className="flex items-center justify-center gap-3"
            fullWidth
            onClick={handleGoogleLogin}
            disabled={isLoading}
          >
            {isLoading ? (
              <Spinner className="h-5 w-5" />
            ) : (
              <>
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  className="h-5 w-5"
                >
                  <path
                    fill="#4285F4"
                    d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                  />
                  <path
                    fill="#34A853"
                    d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                  />
                  <path
                    fill="#FBBC05"
                    d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                  />
                  <path
                    fill="#EA4335"
                    d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                  />
                </svg>
                Google로 로그인
              </>
            )}
          </Button>

          {/* 테스트 모드 안내 */}
          <Typography variant="small" color="gray" className="text-center">
            현재 테스트 모드입니다. 버튼을 클릭하면 테스트 계정으로 로그인됩니다.
          </Typography>
        </CardBody>
      </Card>
    </div>
  );
};

export default LoginPage;
