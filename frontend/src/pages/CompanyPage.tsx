import React from 'react';
import { Typography } from '@material-tailwind/react';
import { useAuthStore } from '../stores/authStore';
import { PreStartupCompanyForm } from '../components/company/PreStartupCompanyForm';
import { CeoCompanyForm } from '../components/company/CeoCompanyForm';
import { CompanyDashboard } from '../components/company/CompanyDashboard';

const CompanyPage: React.FC = () => {
  const { user } = useAuthStore();

  const isPreStartup = user?.type_code === 'U002';

  return (
    <div className="p-6">
      <Typography variant="h4" color="blue-gray" className="mb-6">
        기업 정보
      </Typography>

      {isPreStartup ? <PreStartupCompanyForm /> : <CeoCompanyForm />}

      <CompanyDashboard />
    </div>
  );
};

export default CompanyPage;
