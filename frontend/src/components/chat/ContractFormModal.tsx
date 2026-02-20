import React, { useState } from 'react';
import { XMarkIcon, ChevronDownIcon, ChevronUpIcon } from '@heroicons/react/24/outline';
import { generateContract, downloadDocumentResponse } from '../../lib/documentApi';
import type { ContractFormData } from '../../lib/documentApi';

interface ContractFormModalProps {
  onClose: () => void;
}

const inputClass =
  'w-full px-3 py-2 text-sm border border-gray-300 rounded-lg outline-none transition-colors focus:border-blue-500 focus:ring-1 focus:ring-blue-500';

export const ContractFormModal: React.FC<ContractFormModalProps> = ({ onClose }) => {
  const today = new Date().toISOString().split('T')[0];
  const [showDetail, setShowDetail] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [form, setForm] = useState({
    employee_name: '',
    job_title: '',
    job_description: '',
    contract_start_date: today,
    workplace: '',
    base_salary: '',
    is_permanent: true,
    contract_end_date: '',
    work_start_time: '09:00',
    work_end_time: '18:00',
    rest_time: '12:00-13:00',
    work_days: '월~금',
    payment_date: '25',
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value, type } = e.target;
    if (type === 'checkbox') {
      setForm((prev) => ({ ...prev, [name]: (e.target as HTMLInputElement).checked }));
    } else {
      setForm((prev) => ({ ...prev, [name]: value }));
    }
  };

  const isValid =
    form.employee_name.trim() &&
    form.job_title.trim() &&
    form.job_description.trim() &&
    form.contract_start_date &&
    form.workplace.trim() &&
    Number(form.base_salary) > 0 &&
    (form.is_permanent || form.contract_end_date);

  const handleSubmit = async (format: 'pdf' | 'docx') => {
    if (!isValid) return;
    setLoading(true);
    setError(null);
    try {
      const data: ContractFormData = {
        employee_name: form.employee_name.trim(),
        job_title: form.job_title.trim(),
        job_description: form.job_description.trim(),
        contract_start_date: form.contract_start_date,
        workplace: form.workplace.trim(),
        base_salary: Number(form.base_salary),
        is_permanent: form.is_permanent,
        ...(!form.is_permanent && form.contract_end_date ? { contract_end_date: form.contract_end_date } : {}),
        work_start_time: form.work_start_time,
        work_end_time: form.work_end_time,
        rest_time: form.rest_time,
        work_days: form.work_days,
        payment_date: Number(form.payment_date),
        format,
      };
      const response = await generateContract(data);
      downloadDocumentResponse(response);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : '문서 생성에 실패했습니다.');
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
            <h3 className="text-lg font-semibold text-gray-900">근로계약서 생성</h3>
            <p className="text-xs text-gray-500 mt-1">필수 항목을 입력하면 근로계약서를 자동 생성합니다.</p>
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
          {/* 필수 필드 */}
          <div className="grid grid-cols-2 gap-3">
            <Field label="근로자 이름" required>
              <input
                name="employee_name"
                value={form.employee_name}
                onChange={handleChange}
                placeholder="홍길동"
                className={inputClass}
              />
            </Field>
            <Field label="직위/직책" required>
              <input
                name="job_title"
                value={form.job_title}
                onChange={handleChange}
                placeholder="사원"
                className={inputClass}
              />
            </Field>
          </div>

          <Field label="업무 내용" required>
            <textarea
              name="job_description"
              value={form.job_description}
              onChange={handleChange}
              placeholder="웹 개발 및 유지보수"
              rows={2}
              className={`${inputClass} resize-none`}
            />
          </Field>

          <div className="grid grid-cols-2 gap-3">
            <Field label="계약 시작일" required>
              <input
                name="contract_start_date"
                type="date"
                value={form.contract_start_date}
                onChange={handleChange}
                className={inputClass}
              />
            </Field>
            <Field label="근무 장소" required>
              <input
                name="workplace"
                value={form.workplace}
                onChange={handleChange}
                placeholder="서울시 강남구"
                className={inputClass}
              />
            </Field>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <Field label="기본급 (월, 원)" required>
              <input
                name="base_salary"
                type="number"
                value={form.base_salary}
                onChange={handleChange}
                placeholder="2500000"
                min="0"
                className={inputClass}
              />
            </Field>
            <div className="flex items-end pb-1">
              <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
                <input
                  name="is_permanent"
                  type="checkbox"
                  checked={form.is_permanent}
                  onChange={handleChange}
                  className="rounded border-gray-300"
                />
                무기계약 (정규직)
              </label>
            </div>
          </div>

          {!form.is_permanent && (
            <Field label="계약 종료일" required>
              <input
                name="contract_end_date"
                type="date"
                value={form.contract_end_date}
                onChange={handleChange}
                min={form.contract_start_date}
                className={inputClass}
              />
            </Field>
          )}

          {/* 상세 설정 토글 */}
          <button
            type="button"
            onClick={() => setShowDetail(!showDetail)}
            className="flex items-center gap-1 text-sm text-blue-500 hover:text-blue-600 transition-colors"
          >
            {showDetail ? '상세 설정 접기' : '상세 설정 펼치기'}
            {showDetail ? (
              <ChevronUpIcon className="h-4 w-4" />
            ) : (
              <ChevronDownIcon className="h-4 w-4" />
            )}
          </button>

          {showDetail && (
            <div className="space-y-3 border-t pt-3">
              <div className="grid grid-cols-2 gap-3">
                <Field label="근무 시작">
                  <input name="work_start_time" type="time" value={form.work_start_time} onChange={handleChange} className={inputClass} />
                </Field>
                <Field label="근무 종료">
                  <input name="work_end_time" type="time" value={form.work_end_time} onChange={handleChange} className={inputClass} />
                </Field>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <Field label="휴게 시간">
                  <input name="rest_time" value={form.rest_time} onChange={handleChange} className={inputClass} />
                </Field>
                <Field label="근무 요일">
                  <input name="work_days" value={form.work_days} onChange={handleChange} className={inputClass} />
                </Field>
              </div>
              <Field label="급여일 (매월)">
                <input name="payment_date" type="number" min="1" max="31" value={form.payment_date} onChange={handleChange} className={`${inputClass} w-24`} />
              </Field>
            </div>
          )}

          {error && <p className="text-sm text-red-500">{error}</p>}
        </div>

        {/* Footer */}
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
            disabled={!isValid || loading}
            className="inline-flex items-center gap-1.5 px-4 py-2 text-sm text-blue-600 border border-blue-300 rounded-lg hover:bg-blue-50 transition-colors disabled:opacity-50"
          >
            {loading && <LoadingSpinner />}
            {loading ? '생성중...' : 'DOCX 다운로드'}
          </button>
          <button
            onClick={() => handleSubmit('pdf')}
            disabled={!isValid || loading}
            className="inline-flex items-center gap-1.5 px-4 py-2 text-sm text-white bg-blue-500 rounded-lg hover:bg-blue-600 transition-colors disabled:opacity-50"
          >
            {loading && <LoadingSpinner />}
            {loading ? '생성중...' : 'PDF 다운로드'}
          </button>
        </div>
      </div>
    </div>
  );
};

/** 폼 필드 래퍼 */
const Field: React.FC<{ label: string; required?: boolean; children: React.ReactNode }> = ({
  label,
  required,
  children,
}) => (
  <div>
    <label className="block text-sm font-medium text-gray-700 mb-1">
      {label}
      {required && <span className="text-red-400 ml-0.5">*</span>}
    </label>
    {children}
  </div>
);

/** 로딩 스피너 (작은 크기) */
const LoadingSpinner: React.FC = () => (
  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
  </svg>
);
