import React from 'react';
import { Modal } from '../common/Modal';
import { useAuthStore } from '../../stores/authStore';

interface LoginPromptModalProps {
  onClose: () => void;
}

export const LoginPromptModal: React.FC<LoginPromptModalProps> = ({ onClose }) => {
  const openLoginModal = useAuthStore((s) => s.openLoginModal);

  const handleLogin = () => {
    onClose();
    openLoginModal();
  };

  return (
    <Modal
      open
      onClose={onClose}
      title="로그인 필요"
      size="sm"
      footer={
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
      }
    >
      <p className="text-gray-800 text-sm">
        이 기능은 로그인 사용자만 이용할 수 있습니다.
        <br />
        로그인하시겠습니까?
      </p>
    </Modal>
  );
};
