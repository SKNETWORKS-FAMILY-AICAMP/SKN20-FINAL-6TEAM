import React, { useRef, useState } from 'react';
import { Button, Typography } from '@material-tailwind/react';
import {
  PlusIcon,
} from '@heroicons/react/24/outline';
import { CompanyForm, type CompanyFormHandle } from '../components/company/CompanyForm';
import { CompanyDashboard } from '../components/company/CompanyDashboard';
import { NotificationBell } from '../components/layout/NotificationBell';
import { useAuthStore } from '../stores/authStore';
import type { Company } from '../types';

const CompanyPage: React.FC = () => {
  const [selectedCompany, setSelectedCompany] = useState<Company | null>(null);
  const { isAuthenticated } = useAuthStore();
  const companyFormRef = useRef<CompanyFormHandle>(null);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="border-b bg-white p-4">
        <div className="flex items-center justify-between">
          <div>
            <Typography variant="h5" color="blue-gray" className="!text-gray-900">
              기업 정보
            </Typography>
            <Typography variant="small" color="gray" className="!text-gray-700">
              기업을 선택하면 하단에서 해당 기업 기준 대시보드를 확인할 수 있습니다.
            </Typography>
          </div>
          <div className="flex items-center gap-3">
            {isAuthenticated && <NotificationBell />}
          </div>
        </div>
      </div>

      <div className="min-h-0 flex-1 flex flex-col gap-6 overflow-auto p-4 sm:p-6">
        <section aria-label="기업 목록 섹션" className="shrink-0 space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <div className="h-2 w-2 rounded-full bg-blue-500" />
              <Typography variant="h6" color="blue-gray" className="!text-gray-900">
                기업 목록
              </Typography>
            </div>
            <Button
              size="sm"
              className="flex items-center gap-2"
              onClick={() => companyFormRef.current?.openCreateDialog()}
            >
              <PlusIcon className="h-4 w-4" />
              기업 추가
            </Button>
          </div>

          <CompanyForm
            ref={companyFormRef}
            selectedCompanyId={selectedCompany?.company_id ?? null}
            onSelectCompany={setSelectedCompany}
            showTopAddButton={false}
          />
        </section>

        <section aria-label="기업 대시보드 섹션" className="shrink-0 space-y-3">
          <div className="flex items-center gap-2">
            <div className="h-2 w-2 rounded-full bg-cyan-500" />
            <Typography variant="h6" color="blue-gray" className="!text-gray-900">
              {selectedCompany ? `${selectedCompany.com_name} 대시보드` : '선택 기업 대시보드'}
            </Typography>
          </div>

          <CompanyDashboard selectedCompany={selectedCompany} />
        </section>
      </div>
    </div>
  );
};

export default CompanyPage;
