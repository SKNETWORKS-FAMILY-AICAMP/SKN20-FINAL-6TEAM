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

/** base64 -> Blob -> 다운로드 트리거 */
const downloadBase64File = (
  base64Content: string,
  fileName: string,
  mimeType: string,
) => {
  const byteCharacters = atob(base64Content);
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
