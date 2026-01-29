import React from 'react';
import { Spinner, Typography } from '@material-tailwind/react';

interface LoadingSpinnerProps {
  message?: string;
  fullPage?: boolean;
}

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  message = '로딩 중...',
  fullPage = false,
}) => {
  const content = (
    <div className="flex flex-col items-center justify-center gap-3">
      <Spinner className="h-8 w-8" />
      <Typography variant="small" color="gray">
        {message}
      </Typography>
    </div>
  );

  if (fullPage) {
    return <div className="flex items-center justify-center h-full min-h-[400px]">{content}</div>;
  }

  return <div className="flex items-center justify-center py-10">{content}</div>;
};
