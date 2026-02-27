import React, { useState, useEffect, useCallback } from 'react';
import {
  Card,
  CardBody,
  CardHeader,
  Typography,
  Chip,
  Spinner,
} from '@material-tailwind/react';
import {
  CheckCircleIcon,
  ExclamationTriangleIcon,
  XCircleIcon,
  ArrowPathIcon,
} from '@heroicons/react/24/outline';
import api from '../lib/api';
import type { AdminEvaluationStats, ServerStatusResponse } from '../types';
import { DOMAIN_NAMES } from '../types';
import ResourceChart from '../components/admin/ResourceChart';
import SchedulerStatusTable from '../components/admin/SchedulerStatusTable';
import LogViewer from '../components/admin/LogViewer';
import { PageHeader } from '../components/common/PageHeader';

const STATUS_CONFIG: Record<string, { color: 'green' | 'amber' | 'red'; icon: React.ElementType }> = {
  healthy: { color: 'green', icon: CheckCircleIcon },
  degraded: { color: 'amber', icon: ExclamationTriangleIcon },
  unhealthy: { color: 'red', icon: XCircleIcon },
};

const formatUptime = (seconds: number): string => {
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  if (days > 0) return `${days}일 ${hours}시간 ${mins}분`;
  if (hours > 0) return `${hours}시간 ${mins}분`;
  return `${mins}분`;
};

const AdminDashboardPage: React.FC = () => {
  const [stats, setStats] = useState<AdminEvaluationStats | null>(null);
  const [serverStatus, setServerStatus] = useState<ServerStatusResponse | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);
  const [statusLoading, setStatusLoading] = useState(false);
  const [statsError, setStatsError] = useState<string | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);

  const fetchStats = useCallback(async () => {
    setStatsLoading(true);
    setStatsError(null);
    try {
      const response = await api.get<AdminEvaluationStats>('/admin/histories/stats');
      setStats(response.data);
    } catch (err) {
      setStatsError('통계를 불러오는데 실패했습니다.');
      console.error(err);
    } finally {
      setStatsLoading(false);
    }
  }, []);

  const fetchServerStatus = useCallback(async () => {
    setStatusLoading(true);
    setStatusError(null);
    try {
      const response = await api.get<ServerStatusResponse>('/admin/status');
      setServerStatus(response.data);
      setLastChecked(new Date());
    } catch (err) {
      setStatusError('서버 상태를 불러오는데 실패했습니다.');
      console.error(err);
    } finally {
      setStatusLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStats();
    fetchServerStatus();

    const interval = setInterval(() => {
      fetchStats();
      fetchServerStatus();
    }, 12000);
    return () => clearInterval(interval);
  }, [fetchStats, fetchServerStatus]);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <PageHeader
        title={'\uB300\uC2DC\uBCF4\uB4DC'}
        rightSlot={(
          <button
            onClick={() => { fetchStats(); fetchServerStatus(); }}
            disabled={statsLoading || statusLoading}
            className="p-1.5 rounded hover:bg-gray-100 transition-colors disabled:opacity-50"
            title={'\uC0C8\uB85C\uACE0\uCE68'}
          >
            <ArrowPathIcon
              className={`h-5 w-5 text-gray-500 ${(statsLoading || statusLoading) ? 'animate-spin' : ''}`}
            />
          </button>
        )}
      />

      <div className="min-h-0 flex-1 overflow-auto space-y-6 p-4 sm:p-6">
        {/* 통계 카드 */}
        {(statsLoading && !stats) ? (
          <div className="flex justify-center py-10">
            <Spinner className="h-8 w-8" />
          </div>
        ) : statsError ? (
          <div className="text-center py-4 text-red-500">{statsError}</div>
        ) : stats ? (
          <>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <Card className="p-6 text-center">
                <Typography variant="small" className="text-gray-700">
                  전체 상담
                </Typography>
                <Typography variant="h3" color="blue">
                  {stats.total_count}
                </Typography>
              </Card>
              <Card className="p-6 text-center">
                <Typography variant="small" className="text-gray-700">
                  평가된 상담
                </Typography>
                <Typography variant="h3" color="blue">
                  {stats.evaluated_count}
                </Typography>
              </Card>
              <Card className="p-6 text-center">
                <Typography variant="small" className="text-gray-700">
                  통과
                </Typography>
                <Typography variant="h3" color="green">
                  {stats.passed_count}
                </Typography>
              </Card>
              <Card className="p-6 text-center">
                <Typography variant="small" className="text-gray-700">
                  실패
                </Typography>
                <Typography variant="h3" color="red">
                  {stats.failed_count}
                </Typography>
              </Card>
            </div>

            {/* 평균 점수 */}
            <Card>
              <CardHeader floated={false} shadow={false} className="rounded-none">
                <Typography variant="h6" color="blue-gray" className="!text-gray-900">
                  평균 점수
                </Typography>
              </CardHeader>
              <CardBody>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  <div className="text-center">
                    <Typography variant="small" className="text-gray-700">
                      평균 LLM 점수
                    </Typography>
                    <Typography variant="h4" color="blue">
                      {stats.avg_llm_score?.toFixed(1) ?? '-'}/100
                    </Typography>
                  </div>
                  <div className="text-center">
                    <Typography variant="small" className="text-gray-700">
                      평균 Faithfulness
                    </Typography>
                    <Typography variant="h4" color="blue">
                      {stats.avg_faithfulness?.toFixed(2) ?? '-'}
                    </Typography>
                  </div>
                  <div className="text-center">
                    <Typography variant="small" className="text-gray-700">
                      평균 Answer Relevancy
                    </Typography>
                    <Typography variant="h4" color="blue">
                      {stats.avg_answer_relevancy?.toFixed(2) ?? '-'}
                    </Typography>
                  </div>
                </div>
              </CardBody>
            </Card>

            {/* 도메인별 통계 */}
            <Card>
              <CardHeader floated={false} shadow={false} className="rounded-none">
                <Typography variant="h6" color="blue-gray" className="!text-gray-900">
                  도메인별 상담 수
                </Typography>
              </CardHeader>
              <CardBody>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {Object.entries(stats.domain_counts).map(([domain, count]) => (
                    <div key={domain} className="flex justify-between items-center p-4 bg-gray-50 rounded">
                      <Chip
                        value={DOMAIN_NAMES[domain] || domain}
                        color="blue"
                        variant="ghost"
                      />
                      <Typography variant="h5" color="blue-gray">
                        {count}
                      </Typography>
                    </div>
                  ))}
                </div>
              </CardBody>
            </Card>
          </>
        ) : null}

        {/* ─── 모니터링 섹션 ─── */}

        {/* 리소스 모니터링 */}
        <Card>
          <CardHeader floated={false} shadow={false} className="rounded-none">
            <Typography variant="h6" color="blue-gray" className="!text-gray-900">
              리소스 모니터링
              <span className="ml-2 text-xs font-normal text-gray-400">10초 자동 갱신</span>
            </Typography>
          </CardHeader>
          <CardBody>
            <ResourceChart />
          </CardBody>
        </Card>

        {/* 스케줄러 실행 이력 */}
        <Card>
          <CardHeader floated={false} shadow={false} className="rounded-none">
            <Typography variant="h6" color="blue-gray" className="!text-gray-900">
              스케줄러 실행 이력
              <span className="ml-2 text-xs font-normal text-gray-400">최근 10건 · 10초 자동 갱신</span>
            </Typography>
          </CardHeader>
          <CardBody>
            <SchedulerStatusTable />
          </CardBody>
        </Card>

        {/* 실시간 로그 뷰어 */}
        <Card>
          <CardHeader floated={false} shadow={false} className="rounded-none">
            <Typography variant="h6" color="blue-gray" className="!text-gray-900">
              실시간 로그
            </Typography>
          </CardHeader>
          <CardBody>
            <LogViewer />
          </CardBody>
        </Card>

        {/* 서버 상태 */}
        <Card>
          <CardHeader floated={false} shadow={false} className="rounded-none">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Typography variant="h6" color="blue-gray" className="!text-gray-900">
                  서버 상태
                </Typography>
                <button
                  onClick={fetchServerStatus}
                  disabled={statusLoading}
                  className="p-1 rounded hover:bg-gray-100 transition-colors disabled:opacity-50"
                  title="새로고침"
                >
                  <ArrowPathIcon className={`h-4 w-4 text-gray-500 ${statusLoading ? 'animate-spin' : ''}`} />
                </button>
                {lastChecked && (
                  <Typography variant="small" color="gray" className="!text-gray-700">
                    마지막 확인: {lastChecked.toLocaleTimeString('ko-KR')}
                  </Typography>
                )}
              </div>
              {serverStatus && (
                <div className="flex items-center gap-2">
                  <Typography variant="small" color="gray" className="!text-gray-700">
                    가동 시간: {formatUptime(serverStatus.uptime_seconds)}
                  </Typography>
                  <Chip
                    value={serverStatus.overall_status}
                    color={STATUS_CONFIG[serverStatus.overall_status]?.color || 'gray'}
                    size="sm"
                  />
                </div>
              )}
            </div>
          </CardHeader>
          <CardBody>
            {(statusLoading && !serverStatus) ? (
              <div className="flex justify-center py-10">
                <Spinner className="h-8 w-8" />
              </div>
            ) : statusError ? (
              <div className="text-center py-4 text-red-500">{statusError}</div>
            ) : serverStatus ? (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {serverStatus.services.map((service) => {
                  const config = STATUS_CONFIG[service.status] || STATUS_CONFIG.unhealthy;
                  const Icon = config.icon;
                  return (
                    <Card key={service.name} className="p-4 border">
                      <div className="flex items-center justify-between mb-3">
                        <Typography variant="h6" className="capitalize">
                          {service.name}
                        </Typography>
                        <Icon className={`h-6 w-6 text-${config.color}-500`} />
                      </div>
                      <div className="space-y-1">
                        <div className="flex justify-between text-sm">
                          <span className="text-gray-700">상태</span>
                          <Chip value={service.status} color={config.color} size="sm" />
                        </div>
                        {service.response_time_ms !== null && (
                          <div className="flex justify-between text-sm">
                            <span className="text-gray-700">응답 시간</span>
                            <span>{service.response_time_ms}ms</span>
                          </div>
                        )}
                        {service.name === 'rag' && service.details && (
                          <div className="mt-3 pt-3 border-t space-y-2">
                            {/* VectorDB 컬렉션 */}
                            {!!service.details.vectordb_status && typeof service.details.vectordb_status === 'object' && (
                              <div>
                                <Typography variant="small" className="text-gray-700 mb-1">VectorDB</Typography>
                                <div className="flex flex-wrap gap-1">
                                  {Object.entries(service.details.vectordb_status as Record<string, { count: number }>).map(([col, info]) => (
                                    <Chip key={col} value={`${col}: ${info.count}`} color="blue" size="sm" variant="ghost" />
                                  ))}
                                </div>
                              </div>
                            )}
                            {/* OpenAI 모델 */}
                            {!!service.details.openai_status && typeof service.details.openai_status === 'object' && !!(service.details.openai_status as Record<string, string>).model && (
                              <div className="flex justify-between text-sm">
                                <span className="text-gray-700">모델</span>
                                <Chip value={(service.details.openai_status as Record<string, string>).model} color="blue" size="sm" />
                              </div>
                            )}
                            {/* Feature Flags */}
                            {!!service.details.rag_config && typeof service.details.rag_config === 'object' && (
                              <div>
                                <Typography variant="small" className="text-gray-700 mb-1">설정</Typography>
                                <div className="flex flex-wrap gap-1">
                                  {Object.entries(service.details.rag_config as Record<string, boolean | string>).map(([key, val]) =>
                                    typeof val === 'boolean' ? (
                                      <Chip key={key} value={key.replace(/_/g, ' ')} color={val ? 'green' : 'red'} size="sm" variant="ghost" />
                                    ) : (
                                      <Chip key={key} value={`${key.replace(/_/g, ' ')}: ${val}`} color="blue" size="sm" variant="ghost" />
                                    )
                                  )}
                                </div>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    </Card>
                  );
                })}
              </div>
            ) : null}
          </CardBody>
        </Card>
      </div>
    </div>
  );
};

export default AdminDashboardPage;
