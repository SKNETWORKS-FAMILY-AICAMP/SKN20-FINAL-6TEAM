import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
  fetchDocumentTypes,
  generateDocument,
} from '../../lib/documentApi';
import type { DocumentTypeInfo } from '../../lib/documentApi';
import { useChatStore } from '../../stores/chatStore';
import { generateId } from '../../lib/utils';
import { Modal } from '../common/Modal';
import { useToastStore } from '../../stores/toastStore';
import { useDocumentForm } from '../../hooks/useDocumentForm';

interface DocumentFormModalProps {
  documentType: string;
  onClose: () => void;
}

export const DocumentFormModal: React.FC<DocumentFormModalProps> = ({
  documentType,
  onClose,
}) => {
  const addToast = useToastStore((s) => s.addToast);
  const [typeDef, setTypeDef] = useState<DocumentTypeInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [fetching, setFetching] = useState(true);
  const { formValues, initFormValues, handleChange, isValid, renderField } = useDocumentForm();

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const types = await fetchDocumentTypes();
        if (cancelled) return;
        const found = types.find((t) => t.type_key === documentType);
        if (found) {
          setTypeDef(found);
          initFormValues(found.fields);
        } else {
          addToast({ type: 'error', message: `알 수 없는 문서 유형: ${documentType}` });
        }
      } catch {
        if (!cancelled) addToast({ type: 'error', message: '문서 유형 정보를 불러올 수 없습니다.' });
      } finally {
        if (!cancelled) setFetching(false);
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, [documentType]);

  const handleSubmit = async (format: 'pdf' | 'docx') => {
    if (!typeDef || !isValid(typeDef.fields)) return;
    setLoading(true);
    const targetSessionId = useChatStore.getState().ensureCurrentSession();
    try {
      // number 필드는 숫자로 변환
      const params: Record<string, unknown> = {};
      for (const f of typeDef.fields) {
        const val = formValues[f.name];
        if (val === undefined || val === '') continue;
        params[f.name] = f.field_type === 'number' ? Number(val) : val;
      }
      const response = await generateDocument(documentType, params, format);
      if (!response.success || !response.file_content || !response.file_name) {
        throw new Error(response.message || '문서 생성에 실패했습니다.');
      }
      useChatStore.getState().addMessageToSession(targetSessionId, {
        id: generateId(),
        type: 'assistant',
        content: `**${typeDef.label}**이(가) 생성되었습니다.`,
        agent_code: 'A0000008',
        timestamp: new Date(),
        documentAttachment: {
          fileContent: response.file_content,
          fileName: response.file_name,
          documentType: response.document_type || documentType,
          downloadable: true,
        },
      });
      onClose();
    } catch (err) {
      const message = axios.isAxiosError(err)
        ? err.response?.data?.detail || err.response?.data?.message || '문서 생성에 실패했습니다.'
        : err instanceof Error ? err.message : '문서 생성에 실패했습니다.';
      addToast({ type: 'error', message });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal
      open
      onClose={onClose}
      title={typeDef?.label || '문서 생성'}
      subtitle={typeDef?.description || '필드를 입력하면 문서를 자동 생성합니다.'}
      footer={
        !fetching && typeDef ? (
          <div className="flex justify-end gap-2">
            <button
              onClick={onClose}
              disabled={loading}
              className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-50"
            >
              취소
            </button>
            <button
              onClick={() => handleSubmit('docx')}
              disabled={!isValid(typeDef.fields) || loading}
              className="inline-flex items-center gap-1.5 px-4 py-2 text-sm text-blue-600 border border-blue-300 rounded-lg hover:bg-blue-50 transition-colors disabled:opacity-50"
            >
              {loading && <LoadingSpinner />}
              {loading ? '생성중...' : 'DOCX 다운로드'}
            </button>
            <button
              onClick={() => handleSubmit('pdf')}
              disabled={!isValid(typeDef.fields) || loading}
              className="inline-flex items-center gap-1.5 px-4 py-2 text-sm text-white bg-blue-500 rounded-lg hover:bg-blue-600 transition-colors disabled:opacity-50"
            >
              {loading && <LoadingSpinner />}
              {loading ? '생성중...' : 'PDF 다운로드'}
            </button>
          </div>
        ) : undefined
      }
    >
      <div className="space-y-4">
        {fetching && (
          <p className="text-sm text-gray-500 text-center py-8">문서 유형 정보를 불러오는 중...</p>
        )}

        {!fetching && typeDef && typeDef.fields.length > 0 && (
          <>
            {typeDef.fields.map((field) => (
              <div key={field.name}>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {field.label}
                  {field.required && <span className="text-red-400 ml-0.5">*</span>}
                </label>
                {renderField(field)}
              </div>
            ))}
          </>
        )}
      </div>
    </Modal>
  );
};

const LoadingSpinner: React.FC = () => (
  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
  </svg>
);
