import React, { useEffect } from 'react';
import { Typography } from '@material-tailwind/react';
import { CompanyForm } from '../components/company/CompanyForm';
import { CompanyDashboard } from '../components/company/CompanyDashboard';
import { useCompanyStore } from '../stores/companyStore';

const CompanyPage: React.FC = () => {
  const { fetchCompanies } = useCompanyStore();

  useEffect(() => {
    fetchCompanies();
  }, [fetchCompanies]);

  return (
    <div className="p-6">
      <Typography variant="h4" color="blue-gray" className="mb-6 !text-gray-900">
        기업 정보
      </Typography>
      <CompanyForm />
      <CompanyDashboard />
    </div>
  );
};

export default CompanyPage;
