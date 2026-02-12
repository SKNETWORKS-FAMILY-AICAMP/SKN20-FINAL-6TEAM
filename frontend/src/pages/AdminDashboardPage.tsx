import React, { useState, useEffect } from 'react';
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
} from '@heroicons/react/24/outline';
import api from '../lib/api';
import type { AdminEvaluationStats, ServerStatusResponse } from '../types';
import { DOMAIN_NAMES } from '../types';

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

  useEffect(() => {
    const fetchStats = async () => {
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
    };

    const fetchServerStatus = async () => {
      setStatusLoading(true);
      setStatusError(null);
      try {
        const response = await api.get<ServerStatusResponse>('/admin/status');
        setServerStatus(response.data);
      } catch (err) {
        setStatusError('서버 상태를 불러오는데 실패했습니다.');
        console.error(err);
      } finally {
        setStatusLoading(false);
      }
    };

    fetchStats();
    fetchServerStatus();
  }, []);

  return (
    <div className="p-6">
      <Typography variant="h4" color="blue-gray" className="mb-6">
        대시보드
      </Typography>

      <div className="space-y-6">
        {/* 통계 카드 */}
        {statsLoading ? (
          <div className="flex justify-center py-10">
            <Spinner className="h-8 w-8" />
          </div>
        ) : statsError ? (
          <div className="text-center py-4 text-red-500">{statsError}</div>
        ) : stats ? (
          <>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <Card className="p-6 text-center">
                <Typography variant="small" className="text-gray-500">
                  전체 상담
                </Typography>
                <Typography variant="h3" color="blue">
                  {stats.total_count}
                </Typography>
              </Card>
              <Card className="p-6 text-center">
                <Typography variant="small" className="text-gray-500">
                  평가된 상담
                </Typography>
                <Typography variant="h3" color="blue">
                  {stats.evaluated_count}
                </Typography>
              </Card>
              <Card className="p-6 text-center">
                <Typography variant="small" className="text-gray-500">
                  통과
                </Typography>
                <Typography variant="h3" color="green">
                  {stats.passed_count}
                </Typography>
              </Card>
              <Card className="p-6 text-center">
                <Typography variant="small" className="text-gray-500">
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
                <Typography variant="h6" color="blue-gray">
                  평균 점수
                </Typography>
              </CardHeader>
              <CardBody>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  <div className="text-center">
                    <Typography variant="small" className="text-gray-500">
                      평균 LLM 점수
                    </Typography>
                    <Typography variant="h4" color="blue">
                      {stats.avg_llm_score?.toFixed(1) ?? '-'}/100
                    </Typography>
                  </div>
                  <div className="text-center">
                    <Typography variant="small" className="text-gray-500">
                      평균 Faithfulness
                    </Typography>
                    <Typography variant="h4" color="blue">
                      {stats.avg_faithfulness?.toFixed(2) ?? '-'}
                    </Typography>
                  </div>
                  <div className="text-center">
                    <Typography variant="small" className="text-gray-500">
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
                <Typography variant="h6" color="blue-gray">
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

        {/* 서버 상태 */}
        <Card>
          <CardHeader floated={false} shadow={false} className="rounded-none">
            <div className="flex items-center justify-between">
              <Typography variant="h6" color="blue-gray">
                서버 상태
              </Typography>
              {serverStatus && (
                <div className="flex items-center gap-2">
                  <Typography variant="small" color="gray">
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
            {statusLoading ? (
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
                          <span className="text-gray-500">상태</span>
                          <Chip value={service.status} color={config.color} size="sm" />
                        </div>
                        {service.response_time_ms !== null && (
                          <div className="flex justify-between text-sm">
                            <span className="text-gray-500">응답 시간</span>
                            <span>{service.response_time_ms}ms</span>
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
