import React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { Spinner } from '@material-tailwind/react';
import { useAdminMetrics } from '../../hooks/useAdminMetrics';
import MetricCard from './MetricCard';

/**
 * 서버 리소스 실시간 LineChart + 현재 수치 카드.
 * useAdminMetrics()가 10초마다 데이터를 폴링하고 히스토리를 누적합니다.
 */
const ResourceChart: React.FC = () => {
  const { data: current, history, isLoading, error } = useAdminMetrics();

  if (isLoading && history.length === 0) {
    return (
      <div className="flex justify-center py-10">
        <Spinner className="h-8 w-8" />
      </div>
    );
  }

  if (error && history.length === 0) {
    return (
      <div className="text-center py-6 text-red-500 text-sm">
        메트릭 로드 실패 — 관리자 권한이 필요합니다.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* 현재 수치 카드 */}
      {current && (
        <div className="grid grid-cols-3 gap-3">
          <MetricCard
            label="CPU"
            value={current.cpu_percent}
            subtitle={`${current.cpu_percent.toFixed(1)}%`}
          />
          <MetricCard
            label="메모리"
            value={current.memory_percent}
            subtitle={`${current.memory_used_gb}GB / ${current.memory_total_gb}GB`}
          />
          <MetricCard
            label="디스크"
            value={current.disk_percent}
            subtitle={`${current.disk_used_gb}GB / ${current.disk_total_gb}GB`}
          />
        </div>
      )}

      {/* 실시간 추이 차트 */}
      {history.length > 0 ? (
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={history} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis
              dataKey="time"
              tick={{ fontSize: 10, fill: '#9ca3af' }}
              interval="preserveStartEnd"
            />
            <YAxis domain={[0, 100]} unit="%" tick={{ fontSize: 10, fill: '#9ca3af' }} />
            <Tooltip
              formatter={(v: number) => `${v.toFixed(1)}%`}
              contentStyle={{ fontSize: 12 }}
            />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Line
              type="monotone"
              dataKey="cpu_percent"
              name="CPU"
              stroke="#3B82F6"
              dot={false}
              strokeWidth={2}
            />
            <Line
              type="monotone"
              dataKey="memory_percent"
              name="메모리"
              stroke="#F59E0B"
              dot={false}
              strokeWidth={2}
            />
            <Line
              type="monotone"
              dataKey="disk_percent"
              name="디스크"
              stroke="#EF4444"
              dot={false}
              strokeWidth={2}
            />
          </LineChart>
        </ResponsiveContainer>
      ) : (
        <div className="text-center py-6 text-gray-400 text-sm">
          데이터 수집 중... (10초마다 갱신)
        </div>
      )}
    </div>
  );
};

export default ResourceChart;
