import api from './api';
import type { Company } from '../types';

export interface CompanySaveData {
  com_name: string;
  biz_num: string;
  biz_code: string;
  addr: string;
  open_date: string | null;
}

export interface BizLookupResult {
  found: boolean;
  status?: string;
  com_name?: string;
  addr?: string;
  open_date?: string;
}

export const fetchCompanies = async (): Promise<Company[]> => {
  const response = await api.get('/companies');
  return response.data;
};

export const lookupBizNum = async (bizNum: string): Promise<BizLookupResult> => {
  const response = await api.get('/companies/lookup', {
    params: { biz_num: bizNum },
  });
  return response.data;
};

export const createCompany = async (data: CompanySaveData): Promise<void> => {
  await api.post('/companies', data);
};

export const updateCompany = async (companyId: number, data: CompanySaveData): Promise<void> => {
  await api.put(`/companies/${companyId}`, data);
};

export const deleteCompany = async (companyId: number): Promise<void> => {
  await api.delete(`/companies/${companyId}`);
};

export const toggleMainCompany = async (companyId: number): Promise<void> => {
  await api.patch(`/companies/${companyId}/main`);
};
