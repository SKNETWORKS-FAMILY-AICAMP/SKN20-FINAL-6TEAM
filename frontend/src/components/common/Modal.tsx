import React, { useEffect } from 'react';
import { XMarkIcon } from '@heroicons/react/24/outline';

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  footer?: React.ReactNode;
  children: React.ReactNode;
}

const SIZE_CLASSES: Record<NonNullable<ModalProps['size']>, string> = {
  sm: 'max-w-sm',
  md: 'max-w-lg',
  lg: 'max-w-2xl',
  xl: 'max-w-4xl',
};

export const Modal: React.FC<ModalProps> = ({
  open,
  onClose,
  title,
  subtitle,
  size = 'md',
  footer,
  children,
}) => {
  useEffect(() => {
    if (!open) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };

    document.body.style.overflow = 'hidden';
    window.addEventListener('keydown', handleKeyDown);

    return () => {
      document.body.style.overflow = '';
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div
        className={`relative bg-white rounded-lg shadow-xl w-full ${SIZE_CLASSES[size]} max-h-[90vh] flex flex-col`}
        role="dialog"
        aria-modal
        aria-labelledby="modal-title"
      >
        {/* Header */}
        <div className="flex items-start justify-between px-6 py-4 border-b">
          <div>
            <h3 id="modal-title" className="text-lg font-semibold text-gray-900">
              {title}
            </h3>
            {subtitle && <p className="text-xs text-gray-500 mt-1">{subtitle}</p>}
          </div>
          <button
            onClick={onClose}
            className="rounded p-1 transition-colors hover:bg-gray-100 -mr-1 -mt-1 ml-4"
            title="닫기"
            aria-label="닫기"
          >
            <XMarkIcon className="h-5 w-5 text-gray-500" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-4">{children}</div>

        {/* Footer */}
        {footer && <div className="border-t px-6 py-4">{footer}</div>}
      </div>
    </div>
  );
};
