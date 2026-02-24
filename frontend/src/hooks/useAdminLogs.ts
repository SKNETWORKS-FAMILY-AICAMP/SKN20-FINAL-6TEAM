import { useQuery } from '@tanstack/react-query';
import { fetchAdminLogs } from '../lib/api';
import type { LogPageResponse } from '../types/admin';

/**
 * 지정된 서비스의 로그 파일을 폴링합니다.
 *
 * @param file     로그 파일 ('backend' | 'rag')
 * @param autoRefresh  true이면 10초마다 자동 갱신
 * @param page     페이지 번호 (1 = 최신)
 * @param pageSize 페이지당 줄 수
 */
export const useAdminLogs = (
  file: 'backend' | 'rag',
  autoRefresh = true,
  page = 1,
  pageSize = 100,
) =>
  useQuery<LogPageResponse>({
    queryKey: ['admin', 'logs', file, page, pageSize],
    queryFn: () => fetchAdminLogs(file, page, pageSize).then((r) => r.data),
    refetchInterval: autoRefresh ? 10_000 : false,
    refetchIntervalInBackground: false,
  });
