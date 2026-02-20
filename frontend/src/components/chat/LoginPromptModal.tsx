import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';

interface LoginPromptModalProps {
  onClose: () => void;
}

export const LoginPromptModal: React.FC<LoginPromptModalProps> = ({ onClose }) => {
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogin = () => {
    onClose();
    navigate('/login', { state: { backgroundLocation: location } });
  };

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-white rounded-lg p-6 max-w-sm mx-4 shadow-xl">
        <p className="text-gray-800 text-sm mb-4">
          이 기능은 로그인 사용자만 이용할 수 있습니다.
          <br />
          로그인하시겠습니까?
        </p>
        <div className="flex justify-end gap-2">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
          >
            취소
          </button>
          <button
            onClick={handleLogin}
            className="px-4 py-2 text-sm text-white bg-blue-500 rounded-lg hover:bg-blue-600 transition-colors"
          >
            로그인
          </button>
        </div>
      </div>
    </div>
  );
};
