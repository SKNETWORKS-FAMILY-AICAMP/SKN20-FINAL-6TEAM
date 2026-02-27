import { useQuery } from '@tanstack/react-query';
import { fetchSchedulerStatus } from '../lib/api';
import type { JobLogEntry } from '../types/admin';

/**
 * 스케줄러 작업 실행 이력을 10초마다 폴링합니다.
 */
export const useSchedulerStatus = (limit = 10) =>
  useQuery<JobLogEntry[]>({
    queryKey: ['admin', 'scheduler', limit],
    queryFn: () => fetchSchedulerStatus(limit).then((r) => r.data),
    refetchInterval: 10_000,
    refetchIntervalInBackground: false,
  });
