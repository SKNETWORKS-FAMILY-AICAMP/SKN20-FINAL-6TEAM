import React, { useRef, useState } from 'react';
import { Button, Typography } from '@material-tailwind/react';
import {
  PlusIcon,
} from '@heroicons/react/24/outline';
import { CompanyForm, type CompanyFormHandle } from '../components/company/CompanyForm';
import { CompanyDashboard } from '../components/company/CompanyDashboard';
import { PageHeader } from '../components/common/PageHeader';
import type { Company } from '../types';

const CompanyPage: React.FC = () => {
  const [selectedCompany, setSelectedCompany] = useState<Company | null>(null);
  const companyFormRef = useRef<CompanyFormHandle>(null);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <PageHeader
        title={'\uAE30\uC5C5 \uC815\uBCF4'}
        description={'\uAE30\uC5C5\uC744 \uC120\uD0DD\uD558\uBA74 \uD558\uB2E8\uC5D0\uC11C \uD574\uB2F9 \uAE30\uC5C5 \uAE30\uC900 \uB300\uC2DC\uBCF4\uB4DC\uB97C \uD655\uC778\uD560 \uC218 \uC788\uC2B5\uB2C8\uB2E4.'}
      />

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
