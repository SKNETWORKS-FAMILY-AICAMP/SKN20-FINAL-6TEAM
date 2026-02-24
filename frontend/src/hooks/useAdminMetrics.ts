import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchAdminMetrics } from '../lib/api';
import type { AdminMetrics, MetricDataPoint } from '../types/admin';

const MAX_DATA_POINTS = 30; // 10초 × 30 = 최근 5분

/**
 * 서버 리소스 메트릭을 10초마다 폴링하고 최근 30개 히스토리를 누적합니다.
 */
export const useAdminMetrics = () => {
  const [history, setHistory] = useState<MetricDataPoint[]>([]);

  const query = useQuery<AdminMetrics>({
    queryKey: ['admin', 'metrics'],
    queryFn: () => fetchAdminMetrics().then((r) => r.data),
    refetchInterval: 10_000,
    refetchIntervalInBackground: false,
  });

  useEffect(() => {
    if (!query.data) return;
    const point: MetricDataPoint = {
      ...query.data,
      time: new Date().toLocaleTimeString('ko-KR', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      }),
    };
    setHistory((prev) => [...prev.slice(-(MAX_DATA_POINTS - 1)), point]);
  }, [query.data]);

  return { ...query, history };
};
