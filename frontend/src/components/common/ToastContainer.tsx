import React, { useCallback, useEffect, useRef, useState } from 'react';
import { XMarkIcon, CheckCircleIcon, ExclamationCircleIcon } from '@heroicons/react/24/outline';
import { useToastStore } from '../../stores/toastStore';

const TOAST_AUTO_HIDE_MS = 4000;
const TOAST_EXIT_ANIMATION_MS = 220;

interface ToastItemProps {
  id: string;
  type: 'success' | 'error';
  message: string;
  onRemove: (id: string) => void;
}

const ToastItem: React.FC<ToastItemProps> = ({ id, type, message, onRemove }) => {
  const [isVisible, setIsVisible] = useState(false);
  const isClosingRef = useRef(false);

  const close = useCallback(() => {
    if (isClosingRef.current) return;
    isClosingRef.current = true;
    setIsVisible(false);
    window.setTimeout(() => onRemove(id), TOAST_EXIT_ANIMATION_MS);
  }, [id, onRemove]);

  useEffect(() => {
    const rafId = window.requestAnimationFrame(() => setIsVisible(true));
    const timerId = window.setTimeout(close, TOAST_AUTO_HIDE_MS);
    return () => {
      window.cancelAnimationFrame(rafId);
      window.clearTimeout(timerId);
    };
  }, [close]);

  const isSuccess = type === 'success';
  const Icon = isSuccess ? CheckCircleIcon : ExclamationCircleIcon;
  const colorClass = isSuccess
    ? 'border-green-200 bg-green-50 text-green-800'
    : 'border-red-200 bg-red-50 text-red-800';
  const iconClass = isSuccess ? 'text-green-500' : 'text-red-500';

  return (
    <div
      className={`pointer-events-auto flex items-start gap-3 rounded-xl border px-4 py-3 shadow-xl transition-all duration-200 ${colorClass} ${
        isVisible ? 'translate-y-0 opacity-100' : '-translate-y-3 opacity-0'
      }`}
    >
      <Icon className={`mt-0.5 h-5 w-5 flex-shrink-0 ${iconClass}`} />
      <span className="flex-1 text-sm font-medium">{message}</span>
      <button
        type="button"
        onClick={close}
        className="rounded p-1 opacity-60 transition-colors hover:opacity-100"
        aria-label="닫기"
      >
        <XMarkIcon className="h-4 w-4" />
      </button>
    </div>
  );
};

export const ToastContainer: React.FC = () => {
  const { toasts, removeToast } = useToastStore();

  return (
    <div className="pointer-events-none fixed right-4 top-4 z-[9999] flex w-[min(92vw,22rem)] flex-col gap-2">
      {toasts.map((toast) => (
        <ToastItem key={toast.id} {...toast} onRemove={removeToast} />
      ))}
    </div>
  );
};
