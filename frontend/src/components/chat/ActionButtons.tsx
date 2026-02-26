import React, { useState } from 'react';
import {
  DocumentArrowDownIcon,
  ArrowTopRightOnSquareIcon,
  CalculatorIcon,
  BellIcon,
  MagnifyingGlassIcon,
} from '@heroicons/react/24/outline';
import { useAuthStore } from '../../stores/authStore';
import { ContractFormModal } from './ContractFormModal';
import { DocumentFormModal } from './DocumentFormModal';
import { LoginPromptModal } from './LoginPromptModal';
import type { RagActionSuggestion } from '../../types';

/** LLM 기반 동적 폼을 사용하는 문서 유형 */
const LLM_DOC_TYPES = new Set([
  'business_plan',
  'nda',
  'service_agreement',
  'cofounder_agreement',
  'investment_loi',
  'mou',
  'privacy_consent',
  'shareholders_agreement',
]);

const ACTION_ICONS: Record<string, typeof DocumentArrowDownIcon> = {
  document_generation: DocumentArrowDownIcon,
  external_link: ArrowTopRightOnSquareIcon,
  calculator: CalculatorIcon,
  schedule_alert: BellIcon,
  funding_search: MagnifyingGlassIcon,
};

const DISABLED_TYPES = new Set(['calculator', 'schedule_alert', 'funding_search']);

interface ActionButtonsProps {
  actions: RagActionSuggestion[];
}

export const ActionButtons: React.FC<ActionButtonsProps> = ({ actions }) => {
  const { isAuthenticated } = useAuthStore();
  const [contractModalOpen, setContractModalOpen] = useState(false);
  const [docModalType, setDocModalType] = useState<string | null>(null);
  const [loginPromptOpen, setLoginPromptOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleAction = async (action: RagActionSuggestion) => {
    setError(null);

    // external_link: 비인증 허용 (안전한 프로토콜만)
    if (action.type === 'external_link') {
      const url = action.params.url as string;
      try {
        const parsed = new URL(url);
        if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
          setError('안전하지 않은 링크입니다.');
          return;
        }
      } catch {
        setError('유효하지 않은 링크입니다.');
        return;
      }
      window.open(url, '_blank', 'noopener');
      return;
    }

    // 비활성 타입: 무시
    if (DISABLED_TYPES.has(action.type)) return;

    // 그 외 액션은 인증 필요
    if (!isAuthenticated) {
      setLoginPromptOpen(true);
      return;
    }

    if (action.type === 'document_generation') {
      const docType = action.params.document_type as string;
      if (docType === 'labor_contract') {
        setContractModalOpen(true);
      } else if (LLM_DOC_TYPES.has(docType)) {
        setDocModalType(docType);
      }
    }
  };

  return (
    <>
      <div className="mt-3 pt-2 border-t border-gray-200 flex flex-wrap gap-2">
        {actions.map((action, i) => {
          const Icon = ACTION_ICONS[action.type] || DocumentArrowDownIcon;
          const disabled = DISABLED_TYPES.has(action.type);

          return (
            <button
              key={i}
              onClick={() => handleAction(action)}
              disabled={disabled}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border transition-colors ${
                disabled
                  ? 'border-gray-200 text-gray-400 cursor-not-allowed bg-gray-50'
                  : 'border-blue-200 text-blue-600 hover:bg-blue-50 hover:border-blue-300'
              }`}
              title={disabled ? '추후 지원 예정' : action.label}
            >
              <Icon className="h-4 w-4" />
              {action.label}
              {disabled && <span className="text-[10px] text-gray-400">(예정)</span>}
            </button>
          );
        })}
      </div>

      {error && (
        <p className="mt-1 text-xs text-red-500">{error}</p>
      )}

      {contractModalOpen && (
        <ContractFormModal onClose={() => setContractModalOpen(false)} />
      )}
      {docModalType && (
        <DocumentFormModal
          documentType={docModalType}
          onClose={() => setDocModalType(null)}
        />
      )}
      {loginPromptOpen && (
        <LoginPromptModal onClose={() => setLoginPromptOpen(false)} />
      )}
    </>
  );
};
