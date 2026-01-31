import React from 'react';
import { Typography } from '@material-tailwind/react';
import { CompanyForm } from '../components/company/CompanyForm';
import { CompanyDashboard } from '../components/company/CompanyDashboard';

const CompanyPage: React.FC = () => {
  return (
    <div className="p-6">
      <Typography variant="h4" color="blue-gray" className="mb-6">
        기업 정보
      </Typography>

      <CompanyForm />

      <CompanyDashboard />
    </div>
  );
};

export default CompanyPage;
