import React, { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate, type Location } from 'react-router-dom';
import { Card, CardBody, Typography } from '@material-tailwind/react';
import { XMarkIcon } from '@heroicons/react/24/outline';
import { GoogleLogin, CredentialResponse } from '@react-oauth/google';
import { useAuthStore } from '../stores/authStore';
import api from '../lib/api';
import { extractErrorMessage } from '../lib/errorHandler';

interface LoginRouteState {
  backgroundLocation?: Location;
}

const FEATURE_ITEMS = [
  '.',
  '.',
  '창업 인허가, 지원사업, 재무/회계 상담',
  '인사/노무, 법률 리스크 기본 가이드',
  '기업 프로필 기반 맞춤형 상담 지원',
  '대화 히스토리 기반 연속 상담',
  '.',
  '.',
];

const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { login } = useAuthStore();
  const [error, setError] = useState<string | null>(null);

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

  const handleGoogleSuccess = async (credentialResponse: CredentialResponse) => {
    setError(null);

    try {
      const response = await api.post('/auth/google', {
        id_token: credentialResponse.credential,
      });
      const { user } = response.data;

      await login(user);
      closeModal();
    } catch (err: unknown) {
      console.error('Login error:', err);
      setError(extractErrorMessage(err, '로그인에 실패했습니다.'));
    }
  };

  const handleGoogleError = () => {
    setError('Google 로그인에 실패했습니다. 다시 시도해 주세요.');
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
            aria-label="濡쒓렇??紐⑤떖 ?リ린"
            className="absolute right-5 top-5 z-20 rounded-full border border-gray-200 bg-white p-1.5 text-gray-400 transition-colors hover:text-gray-700"
            onClick={closeModal}
          >
            <XMarkIcon className="h-5 w-5" />
          </button>

          <CardBody className="p-0">
            <div className="chiron-korean-font flex flex-col px-8 pt-10 pb-8">
              <div className="relative mb-1 pb-1">
                <h1 className="brand-logo-font login-brand-logo-offset relative z-10 text-[6.2rem] leading-[0.9] tracking-tight text-indigo-500">
                  Biz
                  <span className="relative inline-block">
                    i
                    <span
                      aria-hidden
                      className="absolute left-[33%] bottom-[0.23em] h-[2px] w-[30rem] bg-indigo-500"
                    />
                  </span>
                </h1>
              </div>

              <Typography variant="paragraph" className="login-welcome-font -mt-6 !text-gray-600">
                ?듯빀 李쎌뾽/寃쎌쁺 ?곷떞 梨쀫큸??
                <br />
                ?ㅼ떊 寃껋쓣 ?섏쁺?⑸땲??
              </Typography>

              <ul className="ml-auto mt-10 w-full max-w-[19rem] space-y-2 text-right text-[10pt] font-normal leading-[1.4] text-[#6BB3F2]">
                {FEATURE_ITEMS.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>

              <Typography variant="paragraph" className="mt-10 text-center !text-gray-600">
                臾댁젣?쒖쑝濡?理쒖쟻?붾맂 ?곷떞 湲곕뒫???댁슜?대낫?몄슂
              </Typography>

              {error && (
                <div className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-center text-sm text-red-600">
                  {error}
                </div>
              )}

              <div className="mt-5 flex justify-center">
                <GoogleLogin
                  onSuccess={handleGoogleSuccess}
                  onError={handleGoogleError}
                  size="large"
                  width="320"
                  text="signin_with"
                  shape="rectangular"
                />
              </div>
            </div>
          </CardBody>
        </Card>
      </div>
    </div>
  );
};

export default LoginPage;

