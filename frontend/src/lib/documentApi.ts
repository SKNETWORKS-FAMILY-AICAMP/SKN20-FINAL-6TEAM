import api from './api';

export interface ContractFormData {
  employee_name: string;
  job_title: string;
  job_description: string;
  contract_start_date: string;
  workplace: string;
  base_salary: number;
  is_permanent?: boolean;
  contract_end_date?: string;
  work_start_time?: string;
  work_end_time?: string;
  rest_time?: string;
  work_days?: string;
  payment_date?: number;
  format?: string;
  // 휴일·휴가
  holidays?: string;
  annual_leave_days?: number;
  // 단시간근로자
  is_part_time?: boolean;
  weekly_work_hours?: number;
  // 임금 상세
  overtime_pay_rate?: number;
  night_pay_rate?: number;
  holiday_pay_rate?: number;
  bonus?: string;
  allowances?: string;
  payment_method?: string;
}

interface DocumentResponse {
  success: boolean;
  file_content?: string;
  file_name?: string;
  document_type?: string;
  message?: string;
}

export const generateContract = async (data: ContractFormData): Promise<DocumentResponse> => {
  const response = await api.post('/rag/documents/contract', data);
  return response.data;
};

export const generateBusinessPlan = async (format = 'docx'): Promise<DocumentResponse> => {
  const response = await api.post(`/rag/documents/business-plan?format=${format}`);
  return response.data;
};

/* ---------- 범용 문서 생성 API ---------- */

export interface DocumentTypeField {
  name: string;
  label: string;
  field_type: 'text' | 'date' | 'number' | 'textarea' | 'select';
  required: boolean;
  placeholder: string;
  options?: string[];
}

export interface DocumentTypeInfo {
  type_key: string;
  label: string;
  description: string;
  fields: DocumentTypeField[];
  default_format: string;
}

export const fetchDocumentTypes = async (): Promise<DocumentTypeInfo[]> => {
  const response = await api.get('/rag/documents/types');
  return response.data;
};

export const generateDocument = async (
  documentType: string,
  params: Record<string, unknown>,
  format?: string,
): Promise<DocumentResponse> => {
  const response = await api.post('/rag/documents/generate', {
    document_type: documentType,
    params,
    format: format || 'docx',
  });
  return response.data;
};

/* ---------- 문서 수정 API ---------- */

export const modifyDocument = async (
  fileContent: string,
  fileName: string,
  instructions: string,
  format?: string,
): Promise<DocumentResponse> => {
  const response = await api.post('/rag/documents/modify', {
    file_content: fileContent,
    file_name: fileName,
    instructions,
    format: format || 'docx',
  });
  return response.data;
};

/** File → base64 문자열 변환 */
export const fileToBase64 = (file: File): Promise<string> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      // "data:...;base64," 접두사 제거
      const base64 = result.split(',')[1];
      resolve(base64);
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
};

/** base64 -> Blob -> 다운로드 트리거 */
const downloadBase64File = (
  base64Content: string,
  fileName: string,
  mimeType: string,
) => {
  let byteCharacters: string;
  try {
    byteCharacters = atob(base64Content);
  } catch {
    throw new Error('파일 데이터가 올바르지 않습니다. 다시 시도해주세요.');
  }
  const byteNumbers = new Array(byteCharacters.length);
  for (let i = 0; i < byteCharacters.length; i++) {
    byteNumbers[i] = byteCharacters.charCodeAt(i);
  }
  const byteArray = new Uint8Array(byteNumbers);
  const blob = new Blob([byteArray], { type: mimeType });

  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = fileName;
  link.click();
  URL.revokeObjectURL(url);
};

const MIME_TYPES: Record<string, string> = {
  pdf: 'application/pdf',
  docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
};

/** 문서 생성 응답에서 파일 다운로드 */
export const downloadDocumentResponse = (response: DocumentResponse) => {
  if (!response.success || !response.file_content || !response.file_name) {
    throw new Error(response.message || '문서 생성에 실패했습니다.');
  }
  const ext = response.file_name.split('.').pop() || 'pdf';
  const mimeType = MIME_TYPES[ext] || 'application/octet-stream';
  downloadBase64File(response.file_content, response.file_name, mimeType);
};
