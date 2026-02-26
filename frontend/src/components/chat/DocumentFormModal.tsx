import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { XMarkIcon } from '@heroicons/react/24/outline';
import {
  fetchDocumentTypes,
  generateDocument,
  downloadDocumentResponse,
} from '../../lib/documentApi';
import type { DocumentTypeInfo, DocumentTypeField } from '../../lib/documentApi';

interface DocumentFormModalProps {
  documentType: string;
  onClose: () => void;
}

const inputClass =
  'w-full px-3 py-2 text-sm border border-gray-300 rounded-lg outline-none transition-colors focus:border-blue-500 focus:ring-1 focus:ring-blue-500';

export const DocumentFormModal: React.FC<DocumentFormModalProps> = ({
  documentType,
  onClose,
}) => {
  const [typeDef, setTypeDef] = useState<DocumentTypeInfo | null>(null);
  const [formValues, setFormValues] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [fetching, setFetching] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const types = await fetchDocumentTypes();
        if (cancelled) return;
        const found = types.find((t) => t.type_key === documentType);
        if (found) {
          setTypeDef(found);
          // 초기값 세팅
          const initial: Record<string, string> = {};
          for (const f of found.fields) {
            initial[f.name] = '';
          }
          setFormValues(initial);
        } else {
          setError(`알 수 없는 문서 유형: ${documentType}`);
        }
      } catch {
        if (!cancelled) setError('문서 유형 정보를 불러올 수 없습니다.');
      } finally {
        if (!cancelled) setFetching(false);
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, [documentType]);

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>,
  ) => {
    const { name, value } = e.target;
    setFormValues((prev) => ({ ...prev, [name]: value }));
  };

  const isValid = (): boolean => {
    if (!typeDef) return false;
    return typeDef.fields
      .filter((f) => f.required)
      .every((f) => {
        const val = formValues[f.name];
        return val !== undefined && val.toString().trim() !== '';
      });
  };

  const handleSubmit = async (format: 'pdf' | 'docx') => {
    if (!isValid() || !typeDef) return;
    setLoading(true);
    setError(null);
    try {
      // number 필드는 숫자로 변환
      const params: Record<string, unknown> = {};
      for (const f of typeDef.fields) {
        const val = formValues[f.name];
        if (val === undefined || val === '') continue;
        params[f.name] = f.field_type === 'number' ? Number(val) : val;
      }
      const response = await generateDocument(documentType, params, format);
      downloadDocumentResponse(response);
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

  const renderField = (field: DocumentTypeField) => {
    const value = formValues[field.name] ?? '';

    if (field.field_type === 'textarea') {
      return (
        <textarea
          name={field.name}
          value={value}
          onChange={handleChange}
          placeholder={field.placeholder}
          rows={3}
          className={`${inputClass} resize-none`}
        />
      );
    }

    if (field.field_type === 'select' && field.options) {
      return (
        <select name={field.name} value={value} onChange={handleChange} className={inputClass}>
          <option value="">선택하세요</option>
          {field.options.map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
      );
    }

    const inputType =
      field.field_type === 'number' ? 'number' : field.field_type === 'date' ? 'date' : 'text';

    return (
      <input
        name={field.name}
        type={inputType}
        value={value}
        onChange={handleChange}
        placeholder={field.placeholder}
        className={inputClass}
      />
    );
  };

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-white rounded-lg shadow-xl w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-white border-b px-6 py-4 rounded-t-lg flex items-start justify-between">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">
              {typeDef?.label || '문서 생성'}
            </h3>
            <p className="text-xs text-gray-500 mt-1">
              {typeDef?.description || '필드를 입력하면 문서를 자동 생성합니다.'}
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

          {error && <p className="text-sm text-red-500">{error}</p>}
        </div>

        {/* Footer */}
        {!fetching && typeDef && (
          <div className="sticky bottom-0 bg-white border-t px-6 py-4 rounded-b-lg flex justify-end gap-2">
            <button
              onClick={onClose}
              disabled={loading}
              className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-50"
            >
              취소
            </button>
            <button
              onClick={() => handleSubmit('docx')}
              disabled={!isValid() || loading}
              className="inline-flex items-center gap-1.5 px-4 py-2 text-sm text-blue-600 border border-blue-300 rounded-lg hover:bg-blue-50 transition-colors disabled:opacity-50"
            >
              {loading && <LoadingSpinner />}
              {loading ? '생성중...' : 'DOCX 다운로드'}
            </button>
            <button
              onClick={() => handleSubmit('pdf')}
              disabled={!isValid() || loading}
              className="inline-flex items-center gap-1.5 px-4 py-2 text-sm text-white bg-blue-500 rounded-lg hover:bg-blue-600 transition-colors disabled:opacity-50"
            >
              {loading && <LoadingSpinner />}
              {loading ? '생성중...' : 'PDF 다운로드'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

const LoadingSpinner: React.FC = () => (
  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
  </svg>
);
