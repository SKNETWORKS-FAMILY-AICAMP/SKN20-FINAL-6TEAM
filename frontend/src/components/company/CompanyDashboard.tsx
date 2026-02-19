import React from 'react';
import { Card, CardBody, Typography } from '@material-tailwind/react';
import {
  NewspaperIcon,
  CalendarDaysIcon,
  MegaphoneIcon,
} from '@heroicons/react/24/outline';

const DASHBOARD_CARDS = [
  {
    title: '최근 공고',
    description: '우리 기업에 맞는 최근 정부 지원사업 공고를 확인하세요.',
    icon: MegaphoneIcon,
    color: 'text-blue-500',
    bgColor: 'bg-blue-50',
  },
  {
    title: '다가오는 일정',
    description: '세금 신고, 지원사업 마감 등 주요 일정을 확인하세요.',
    icon: CalendarDaysIcon,
    color: 'text-green-500',
    bgColor: 'bg-green-50',
  },
  {
    title: '관련 뉴스',
    description: '업종 관련 최신 정책 및 경영 뉴스를 확인하세요.',
    icon: NewspaperIcon,
    color: 'text-purple-500',
    bgColor: 'bg-purple-50',
  },
];

export const CompanyDashboard: React.FC = () => {
  return (
    <div className="mt-8">
      <Typography variant="h5" color="blue-gray" className="mb-4 !text-gray-900">
        기업 대시보드
      </Typography>
      <div className="grid gap-4 md:grid-cols-3">
        {DASHBOARD_CARDS.map((card) => (
          <Card key={card.title} className="cursor-pointer hover:shadow-lg transition-shadow">
            <CardBody className="text-center">
              <div className={`inline-flex p-3 rounded-full ${card.bgColor} mb-3`}>
                <card.icon className={`h-8 w-8 ${card.color}`} />
              </div>
              <Typography variant="h6" color="blue-gray" className="mb-2 !text-gray-900">
                {card.title}
              </Typography>
              <Typography variant="small" color="gray" className="!text-gray-700">
                {card.description}
              </Typography>
              <Typography variant="small" color="gray" className="mt-3 text-xs italic !text-gray-600">
                준비 중...
              </Typography>
            </CardBody>
          </Card>
        ))}
      </div>
    </div>
  );
};
