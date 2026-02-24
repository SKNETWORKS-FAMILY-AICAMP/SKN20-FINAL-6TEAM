/** 관리자 모니터링 관련 TypeScript 타입 정의. */

export interface AdminMetrics {
  cpu_percent: number;
  memory_percent: number;
  disk_percent: number;
  memory_total_gb: number;
  memory_used_gb: number;
  disk_total_gb: number;
  disk_used_gb: number;
  timestamp: string;
}

export type JobStatus = 'started' | 'success' | 'failed';

export interface JobLogEntry {
  id: number;
  job_name: string;
  status: JobStatus;
  started_at: string;
  finished_at: string | null;
  duration_ms: number | null;
  record_count: number | null;
  error_msg: string | null;
}

export interface LogPageResponse {
  total_lines: number;
  page: number;
  page_size: number;
  lines: string[];
  file: string;
}

/** ResourceChart가 누적하는 히스토리 데이터 포인트. */
export interface MetricDataPoint extends AdminMetrics {
  /** 표시용 시각 (HH:MM:SS) */
  time: string;
}
