import React, { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate, type Location } from 'react-router-dom';
import { Card, CardBody, Typography } from '@material-tailwind/react';
import { XMarkIcon } from '@heroicons/react/24/outline';
import { useAuthStore } from '../stores/authStore';
import api from '../lib/api';
import { extractErrorMessage } from '../lib/errorHandler';

interface LoginRouteState {
  backgroundLocation?: Location;
}

const FEATURE_ITEMS = [
  '창업 절차, 지원사업, 세무/회계 상담',
  '인사/노무, 법률 리스크 기본 가이드',
  '기업 프로필 기반 맞춤형 상담 지원',
  '대화 히스토리 기반 연속 상담',
];

const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { login } = useAuthStore();
  const [error, setError] = useState<string | null>(null);
  const [adminLoading, setAdminLoading] = useState(false);

  const hasBackgroundLocation = useMemo(() => {
    const state = location.state as LoginRouteState | null;
    return Boolean(state?.backgroundLocation);
  }, [location.state]);

  const closeModal = () => {
    if (hasBackgroundLocation) {
      navigate(-1);
      return;
    }
    navigate('/', { replace: true });
  };

  useEffect(() => {
    const handleKeydown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') {
        return;
      }

      if (hasBackgroundLocation) {
        navigate(-1);
        return;
      }

      navigate('/', { replace: true });
    };

    window.addEventListener('keydown', handleKeydown);
    return () => {
      window.removeEventListener('keydown', handleKeydown);
    };
  }, [hasBackgroundLocation, navigate]);

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
      closeModal();
    } catch (err: unknown) {
      console.error('Login error:', err);
      setError(
        extractErrorMessage(
          err,
          '관리자 테스트 로그인에 실패했습니다. ENABLE_TEST_LOGIN 설정을 확인해 주세요.',
        ),
      );
    } finally {
      setAdminLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[80]">
      <div
        aria-hidden
        className="absolute inset-0"
        style={{ backgroundColor: 'rgba(15, 23, 42, 0.78)' }}
        onClick={closeModal}
      />

      <div className="relative z-10 flex min-h-full items-center justify-center p-4 sm:p-6">
        <Card
          className="relative w-full max-w-[25.5rem] overflow-hidden rounded-md border border-gray-200 bg-white shadow-2xl"
          onClick={(event) => event.stopPropagation()}
        >
          <button
            type="button"
            aria-label="로그인 모달 닫기"
            className="absolute right-5 top-5 z-20 rounded-full border border-gray-200 bg-white p-1.5 text-gray-400 transition-colors hover:text-gray-700"
            onClick={closeModal}
          >
            <XMarkIcon className="h-5 w-5" />
          </button>

          <CardBody className="p-0">
            <div className="flex flex-col px-8 pt-10 pb-8">
              <div className="relative mb-1 pb-1">
                <h1 className="relative z-10 font-serif text-[6.2rem] leading-[0.9] tracking-tight text-indigo-500">
                  Biz
                  <span className="relative inline-block">
                    i
                    <span
                      aria-hidden
                      className="absolute left-[33%] bottom-[0.12em] h-[2px] w-[30rem] bg-indigo-500"
                    />
                  </span>
                </h1>
              </div>

              <Typography variant="paragraph" className="mt-1 !text-gray-600">
                통합 창업/경영 상담 챗봇에
                <br />
                오신 것을 환영합니다.
              </Typography>

              <ul className="ml-auto mt-10 w-full max-w-[19rem] space-y-2 text-right text-[10pt] font-normal leading-[1.4] text-[#6BB3F2]">
                {FEATURE_ITEMS.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>

              <Typography variant="paragraph" className="mt-10 text-center !text-gray-600">
                무제한으로 최적화된 상담 기능을 이용해보세요
              </Typography>

              {error && (
                <div className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-center text-sm text-red-600">
                  {error}
                </div>
              )}

              <div className="mt-5 flex justify-center">
                <button
                  type="button"
                  className="w-[320px] rounded-md border border-gray-300 bg-white px-4 py-2.5 text-base font-medium text-gray-800 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-60"
                  onClick={handleAdminLogin}
                  disabled={adminLoading}
                >
                  {adminLoading ? '로그인 중...' : '관리자 계정으로 로그인'}
                </button>
              </div>
            </div>
          </CardBody>
        </Card>
      </div>
    </div>
  );
};

export default LoginPage;
