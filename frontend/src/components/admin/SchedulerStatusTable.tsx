import React from 'react';
import { Spinner } from '@material-tailwind/react';
import { useSchedulerStatus } from '../../hooks/useSchedulerStatus';
import type { JobStatus } from '../../types/admin';

const STATUS_BADGE: Record<JobStatus, string> = {
  started: 'bg-yellow-100 text-yellow-800',
  success: 'bg-green-100 text-green-800',
  failed:  'bg-red-100 text-red-800',
};

const STATUS_LABEL: Record<JobStatus, string> = {
  started: '실행 중',
  success: '성공',
  failed:  '실패',
};

const formatDuration = (ms: number | null): string => {
  if (ms == null) return '-';
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
};

/**
 * 스케줄러 작업 실행 이력 테이블.
 * 상태(started/success/failed)에 따라 배지 색상이 다릅니다.
 * 10초마다 자동 갱신됩니다.
 */
const SchedulerStatusTable: React.FC = () => {
  const { data: logs = [], isLoading, error } = useSchedulerStatus();

  if (isLoading) {
    return (
      <div className="flex justify-center py-8">
        <Spinner className="h-6 w-6" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-6 text-red-500 text-sm">
        실행 이력 로드 실패
      </div>
    );
  }

  if (logs.length === 0) {
    return (
      <div className="text-center py-8 text-gray-400 text-sm">
        기록된 작업이 없습니다.
        <br />
        <span className="text-xs">스케줄러 작업이 실행되면 자동으로 표시됩니다.</span>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="bg-gray-50 text-left text-xs text-gray-500 uppercase tracking-wide">
            <th className="px-4 py-2">작업명</th>
            <th className="px-4 py-2">상태</th>
            <th className="px-4 py-2">시작 시각</th>
            <th className="px-4 py-2">소요 시간</th>
            <th className="px-4 py-2">처리 건수</th>
            <th className="px-4 py-2">오류 메시지</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {logs.map((log) => {
            const status = log.status as JobStatus;
            return (
              <tr key={log.id} className="hover:bg-gray-50">
                <td className="px-4 py-2 font-mono text-gray-800">{log.job_name}</td>
                <td className="px-4 py-2">
                  <span
                    className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${
                      STATUS_BADGE[status] ?? 'bg-gray-100 text-gray-600'
                    }`}
                  >
                    {STATUS_LABEL[status] ?? log.status}
                  </span>
                </td>
                <td className="px-4 py-2 text-gray-500 whitespace-nowrap">
                  {new Date(log.started_at).toLocaleString('ko-KR')}
                </td>
                <td className="px-4 py-2 text-gray-600">
                  {formatDuration(log.duration_ms)}
                </td>
                <td className="px-4 py-2 text-gray-600">
                  {log.record_count ?? '-'}
                </td>
                <td className="px-4 py-2 text-red-500 text-xs max-w-xs truncate">
                  {log.error_msg ?? '-'}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

export default SchedulerStatusTable;
