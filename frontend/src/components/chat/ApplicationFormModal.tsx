import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { XMarkIcon } from '@heroicons/react/24/outline';
import {
  listApplicationForms,
  analyzeApplicationForm,
  generateDocument,
} from '../../lib/documentApi';
import type { ApplicationFormItem, ApplicationFormAnalysis } from '../../lib/documentApi';
import { useChatStore } from '../../stores/chatStore';
import { generateId } from '../../lib/utils';
import { useDocumentForm } from '../../hooks/useDocumentForm';

interface ApplicationFormModalProps {
  onClose: () => void;
}

type Step = 'select' | 'analyze' | 'fill';

export const ApplicationFormModal: React.FC<ApplicationFormModalProps> = ({ onClose }) => {
  const [step, setStep] = useState<Step>('select');
  const [forms, setForms] = useState<ApplicationFormItem[]>([]);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<ApplicationFormAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [fetching, setFetching] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { formValues, initFormValues, handleChange, isValid, renderField } = useDocumentForm();

  // 양식 목록 로드
  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const items = await listApplicationForms();
        if (!cancelled) setForms(items);
      } catch {
        if (!cancelled) setError('양식 목록을 불러올 수 없습니다.');
      } finally {
        if (!cancelled) setFetching(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, []);

  // 양식 선택 → LLM 분석
  const handleSelectForm = async (key: string) => {
    setSelectedKey(key);
    setStep('analyze');
    setLoading(true);
    setError(null);
    try {
      const result = await analyzeApplicationForm(key);
      setAnalysis(result);
      initFormValues(result.fields);
      setStep('fill');
    } catch {
      setError('양식 분석에 실패했습니다. 다시 시도해주세요.');
      setStep('select');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (format: 'pdf' | 'docx') => {
    if (!analysis || !isValid(analysis.fields)) return;
    setLoading(true);
    setError(null);
    const targetSessionId = useChatStore.getState().ensureCurrentSession();
    try {
      const params: Record<string, unknown> = {};
      for (const f of analysis.fields) {
        const val = formValues[f.name];
        if (val === undefined || val === '') continue;
        params[f.name] = f.field_type === 'number' ? Number(val) : val;
      }
      // 원본 양식 키·제목을 함께 전달하여 executor가 S3 양식을 참조할 수 있도록 함
      params['_form_key'] = selectedKey;
      params['_form_title'] = analysis.title;
      const response = await generateDocument('application_form', params, format);
      if (!response.success || !response.file_content || !response.file_name) {
        throw new Error(response.message || '문서 생성에 실패했습니다.');
      }
      useChatStore.getState().addMessageToSession(targetSessionId, {
        id: generateId(),
        type: 'assistant',
        content: `**${analysis.title}** 신청서가 생성되었습니다.`,
        agent_code: 'A0000008',
        timestamp: new Date(),
        documentAttachment: {
          fileContent: response.file_content,
          fileName: response.file_name,
          documentType: response.document_type || 'application_form',
          downloadable: true,
        },
      });
      onClose();
    } catch (err) {
      if (axios.isAxiosError(err)) {
        setError(
          err.response?.data?.detail ||
            err.response?.data?.message ||
            '문서 생성에 실패했습니다.',
        );
      } else {
        setError(err instanceof Error ? err.message : '문서 생성에 실패했습니다.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-white rounded-lg shadow-xl w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-white border-b px-6 py-4 rounded-t-lg flex items-start justify-between">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">
              {step === 'fill' && analysis ? analysis.title : '신청 양식 선택'}
            </h3>
            <p className="text-xs text-gray-500 mt-1">
              {step === 'fill' && analysis
                ? analysis.description
                : 'S3에 저장된 양식을 선택하면 자동으로 분석합니다.'}
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded p-1 transition-colors hover:bg-gray-100 -mr-1 -mt-1"
            title="닫기"
          >
            <XMarkIcon className="h-5 w-5 text-gray-500" />
          </button>
        </div>

        <div className="px-6 py-4 space-y-4">
          {/* Step: select */}
          {step === 'select' && fetching && (
            <p className="text-sm text-gray-500 text-center py-8">양식 목록을 불러오는 중...</p>
          )}

          {step === 'select' && !fetching && forms.length === 0 && (
            <p className="text-sm text-gray-500 text-center py-8">사용 가능한 양식이 없습니다.</p>
          )}

          {step === 'select' && !fetching && forms.length > 0 && (
            <ul className="space-y-2">
              {forms.map((form) => (
                <li key={form.key}>
                  <button
                    onClick={() => handleSelectForm(form.key)}
                    className="w-full text-left px-4 py-3 border border-gray-200 rounded-lg hover:bg-blue-50 hover:border-blue-300 transition-colors text-sm"
                  >
                    {form.name}
                  </button>
                </li>
              ))}
            </ul>
          )}

          {/* Step: analyze (loading) */}
          {step === 'analyze' && loading && (
            <div className="text-center py-8">
              <LoadingSpinner />
              <p className="text-sm text-gray-500 mt-2">양식을 분석하고 있습니다...</p>
            </div>
          )}

          {/* Step: fill */}
          {step === 'fill' && analysis && analysis.fields.length > 0 && (
            <>
              {analysis.fields.map((field) => (
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

          {error && <p className="text-sm text-red-500">{error}</p>}
        </div>

        {/* Footer */}
        {step === 'fill' && analysis && (
          <div className="sticky bottom-0 bg-white border-t px-6 py-4 rounded-b-lg flex justify-end gap-2">
            <button
              onClick={() => { setStep('select'); setAnalysis(null); setSelectedKey(null); }}
              disabled={loading}
              className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-50"
            >
              양식 재선택
            </button>
            <button
              onClick={() => handleSubmit('docx')}
              disabled={!isValid(analysis.fields) || loading}
              className="inline-flex items-center gap-1.5 px-4 py-2 text-sm text-blue-600 border border-blue-300 rounded-lg hover:bg-blue-50 transition-colors disabled:opacity-50"
            >
              {loading ? '생성중...' : 'DOCX 다운로드'}
            </button>
            <button
              onClick={() => handleSubmit('pdf')}
              disabled={!isValid(analysis.fields) || loading}
              className="inline-flex items-center gap-1.5 px-4 py-2 text-sm text-white bg-blue-500 rounded-lg hover:bg-blue-600 transition-colors disabled:opacity-50"
            >
              {loading ? '생성중...' : 'PDF 다운로드'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

const LoadingSpinner: React.FC = () => (
  <svg className="animate-spin h-6 w-6 text-blue-500 mx-auto" viewBox="0 0 24 24" fill="none">
    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
  </svg>
);
