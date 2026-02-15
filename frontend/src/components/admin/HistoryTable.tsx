import React from 'react';
import {
  Card,
  CardBody,
  CardHeader,
  Typography,
  Button,
  Chip,
  Spinner,
} from '@material-tailwind/react';
import { CheckCircleIcon, XCircleIcon } from '@heroicons/react/24/outline';
import type { AdminHistoryListResponse } from '../../types';
import { DOMAIN_NAMES } from '../../types';
import { formatDateTime } from '../../lib/dateUtils';

const DOMAIN_CHIP_COLORS: Record<string, 'green' | 'purple' | 'amber' | 'red' | 'blue'> = {
  startup_funding: 'green',
  finance_tax: 'purple',
  hr_labor: 'amber',
  law_common: 'red',
};

const calcF1 = (cp: number | null, cr: number | null): number | null => {
  if (cp === null || cr === null || cp + cr === 0) return null;
  return (2 * cp * cr) / (cp + cr);
};

interface HistoryTableProps {
  data: AdminHistoryListResponse | null;
  loading: boolean;
  error: string | null;
  onRowClick: (historyId: number) => void;
  onPageChange: (page: number) => void;
}

export const HistoryTable: React.FC<HistoryTableProps> = ({
  data,
  loading,
  error,
  onRowClick,
  onPageChange,
}) => {
  return (
    <Card>
      <CardHeader floated={false} shadow={false} className="rounded-none">
        <Typography variant="h6" color="blue-gray">
          상담 이력 ({data?.total || 0}건)
        </Typography>
      </CardHeader>
      <CardBody className="overflow-x-auto px-0">
        {loading ? (
          <div className="flex justify-center py-10">
            <Spinner className="h-8 w-8" />
          </div>
        ) : error ? (
          <div className="text-center py-10 text-red-500">{error}</div>
        ) : (
          <>
            <table className="w-full min-w-max table-auto text-left">
              <thead>
                <tr>
                  <th className="border-b border-blue-gray-100 bg-blue-gray-50 p-4">ID</th>
                  <th className="border-b border-blue-gray-100 bg-blue-gray-50 p-4">사용자</th>
                  <th className="border-b border-blue-gray-100 bg-blue-gray-50 p-4">도메인</th>
                  <th className="border-b border-blue-gray-100 bg-blue-gray-50 p-4">질문</th>
                  <th className="border-b border-blue-gray-100 bg-blue-gray-50 p-4">LLM 점수</th>
                  <th className="border-b border-blue-gray-100 bg-blue-gray-50 p-4">RAGAS F1</th>
                  <th className="border-b border-blue-gray-100 bg-blue-gray-50 p-4">응답시간</th>
                  <th className="border-b border-blue-gray-100 bg-blue-gray-50 p-4">일시</th>
                </tr>
              </thead>
              <tbody>
                {data?.items.map((item) => {
                  const f1 = calcF1(item.context_precision, item.context_recall);
                  return (
                    <tr
                      key={item.history_id}
                      className="hover:bg-blue-gray-50 cursor-pointer"
                      onClick={() => onRowClick(item.history_id)}
                    >
                      <td className="p-4 border-b border-blue-gray-50">
                        <Typography variant="small" color="blue-gray" className="font-normal">
                          {item.history_id}
                        </Typography>
                      </td>
                      <td className="p-4 border-b border-blue-gray-50">
                        <Typography variant="small" color="blue-gray" className="font-normal">
                          {item.username || item.user_email || '-'}
                        </Typography>
                      </td>
                      <td className="p-4 border-b border-blue-gray-50">
                        <div className="flex flex-wrap gap-1">
                          {item.domains.map((domain) => (
                            <Chip
                              key={domain}
                              value={DOMAIN_NAMES[domain] || domain}
                              size="sm"
                              variant="ghost"
                              color={DOMAIN_CHIP_COLORS[domain] || 'blue'}
                            />
                          ))}
                        </div>
                      </td>
                      <td className="p-4 border-b border-blue-gray-50 max-w-xs">
                        <Typography
                          variant="small"
                          color="blue-gray"
                          className="font-normal truncate"
                        >
                          {item.question?.slice(0, 50)}{item.question && item.question.length > 50 ? '...' : ''}
                        </Typography>
                      </td>
                      <td className="p-4 border-b border-blue-gray-50">
                        <div className="flex items-center gap-2">
                          {item.llm_passed !== null && (
                            item.llm_passed ? (
                              <CheckCircleIcon className="h-4 w-4 text-green-500" />
                            ) : (
                              <XCircleIcon className="h-4 w-4 text-red-500" />
                            )
                          )}
                          <Typography variant="small" color="blue-gray" className="font-normal">
                            {item.llm_score !== null ? `${item.llm_score}/100` : '-'}
                          </Typography>
                        </div>
                      </td>
                      <td className="p-4 border-b border-blue-gray-50">
                        <Typography variant="small" color="blue-gray" className="font-normal">
                          {f1 !== null ? f1.toFixed(2) : '-'}
                        </Typography>
                      </td>
                      <td className="p-4 border-b border-blue-gray-50">
                        <Typography variant="small" color="blue-gray" className="font-normal">
                          {item.response_time !== null ? `${item.response_time.toFixed(1)}s` : '-'}
                        </Typography>
                      </td>
                      <td className="p-4 border-b border-blue-gray-50">
                        <Typography variant="small" color="blue-gray" className="font-normal">
                          {item.create_date
                            ? formatDateTime(item.create_date)
                            : '-'}
                        </Typography>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>

            {/* Pagination */}
            {data && data.total_pages > 1 && (
              <div className="flex justify-center gap-2 mt-4 p-4">
                <Button
                  variant="outlined"
                  size="sm"
                  disabled={data.page === 1}
                  onClick={() => onPageChange(data.page - 1)}
                >
                  이전
                </Button>
                <Typography className="flex items-center px-4">
                  {data.page} / {data.total_pages}
                </Typography>
                <Button
                  variant="outlined"
                  size="sm"
                  disabled={data.page === data.total_pages}
                  onClick={() => onPageChange(data.page + 1)}
                >
                  다음
                </Button>
              </div>
            )}
          </>
        )}
      </CardBody>
    </Card>
  );
};
