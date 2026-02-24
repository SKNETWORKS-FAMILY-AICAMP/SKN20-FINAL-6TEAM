import { create } from 'zustand';
import api from '../lib/api';
import type { Company } from '../types';

interface CompanyStoreState {
  companies: Company[];
  selectedCompanyId: number | null;
  isLoading: boolean;
  fetchCompanies: () => Promise<void>;
  setMainCompany: (id: number) => Promise<void>;
  selectCompany: (id: number) => void;
}

export const useCompanyStore = create<CompanyStoreState>((set, get) => ({
  companies: [],
  selectedCompanyId: null,
  isLoading: false,

  fetchCompanies: async () => {
    set({ isLoading: true });
    try {
      const response = await api.get('/companies');
      const companies: Company[] = response.data;
      set({ companies });

      // 메인 기업 자동 선택; 없으면 첫 번째 기업 선택
      const main = companies.find((c) => c.main_yn);
      const currentId = get().selectedCompanyId;
      if (main) {
        set({ selectedCompanyId: main.company_id });
      } else if (companies.length > 0 && !currentId) {
        set({ selectedCompanyId: companies[0].company_id });
      } else if (companies.length === 0) {
        set({ selectedCompanyId: null });
      }
    } catch (err) {
      console.error('Failed to fetch companies:', err);
    } finally {
      set({ isLoading: false });
    }
  },

  setMainCompany: async (id: number) => {
    try {
      await api.put(`/companies/${id}`, { main_yn: true });
      await get().fetchCompanies();
    } catch (err) {
      console.error('Failed to set main company:', err);
    }
  },

  selectCompany: (id: number) => {
    set({ selectedCompanyId: id });
  },
}));
