import React, { useState, useEffect } from 'react';
import {
  Card,
  CardBody,
  CardHeader,
  Typography,
  Tabs,
  TabsHeader,
  TabsBody,
  Tab,
  TabPanel,
  Button,
  Chip,
  Dialog,
  DialogHeader,
  DialogBody,
  DialogFooter,
  Input,
  Select,
  Option,
  Spinner,
} from '@material-tailwind/react';
import {
  ChatBubbleLeftRightIcon,
  ChartBarIcon,
  XMarkIcon,
  MagnifyingGlassIcon,
  CheckCircleIcon,
  XCircleIcon,
} from '@heroicons/react/24/outline';
import api from '../lib/api';
import type {
  AdminHistoryListItem,
  AdminHistoryListResponse,
  AdminHistoryDetail,
  AdminEvaluationStats,
  AdminHistoryFilters,
} from '../types';
import { DOMAIN_NAMES } from '../types';

const AdminPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState('logs');

  const tabs = [
    { value: 'logs', label: '상담 로그', icon: ChatBubbleLeftRightIcon },
    { value: 'stats', label: '평가 통계', icon: ChartBarIcon },
  ];

  return (
    <div className="p-6">
      <Typography variant="h4" color="blue-gray" className="mb-6">
        관리자
      </Typography>

      <Tabs value={activeTab}>
        <TabsHeader>
          {tabs.map(({ value, label, icon: Icon }) => (
            <Tab key={value} value={value} onClick={() => setActiveTab(value)}>
              <div className="flex items-center gap-2">
                <Icon className="h-4 w-4" />
                {label}
              </div>
            </Tab>
          ))}
        </TabsHeader>
        <TabsBody>
          <TabPanel value="logs">
            <HistoryLogPanel />
          </TabPanel>
          <TabPanel value="stats">
            <EvaluationStatsPanel />
          </TabPanel>
        </TabsBody>
      </Tabs>
    </div>
  );
};

const HistoryLogPanel: React.FC = () => {
  const [data, setData] = useState<AdminHistoryListResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<AdminHistoryFilters>({
    page: 1,
    page_size: 10,
  });
  const [selectedHistory, setSelectedHistory] = useState<AdminHistoryDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const fetchHistories = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      Object.entries(filters).forEach(([key, value]) => {
        if (value !== undefined && value !== '') {
          params.append(key, String(value));
        }
      });
      const response = await api.get<AdminHistoryListResponse>(
        `/admin/histories?${params.toString()}`
      );
      setData(response.data);
    } catch (err) {
      setError('상담 이력을 불러오는데 실패했습니다.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const fetchHistoryDetail = async (historyId: number) => {
    setDetailLoading(true);
    try {
      const response = await api.get<AdminHistoryDetail>(`/admin/histories/${historyId}`);
      setSelectedHistory(response.data);
    } catch (err) {
      console.error(err);
    } finally {
      setDetailLoading(false);
    }
  };

  useEffect(() => {
    fetchHistories();
  }, [filters.page]);

  const handleSearch = () => {
    setFilters((prev) => ({ ...prev, page: 1 }));
    fetchHistories();
  };

  const handlePageChange = (newPage: number) => {
    setFilters((prev) => ({ ...prev, page: newPage }));
  };

  return (
    <div className="space-y-4">
      {/* Filters */}
      <Card>
        <CardBody>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <Select
              label="도메인"
              value={filters.domain || ''}
              onChange={(value) => setFilters((prev) => ({ ...prev, domain: value || undefined }))}
            >
              <Option value="">전체</Option>
              <Option value="startup_funding">창업/지원</Option>
              <Option value="finance_tax">재무/세무</Option>
              <Option value="hr_labor">인사/노무</Option>
            </Select>
            <Input
              label="최소 LLM 점수"
              type="number"
              value={filters.min_score?.toString() || ''}
              onChange={(e) =>
                setFilters((prev) => ({
                  ...prev,
                  min_score: e.target.value ? parseInt(e.target.value) : undefined,
                }))
              }
              crossOrigin={undefined}
            />
            <Input
              label="최대 LLM 점수"
              type="number"
              value={filters.max_score?.toString() || ''}
              onChange={(e) =>
                setFilters((prev) => ({
                  ...prev,
                  max_score: e.target.value ? parseInt(e.target.value) : undefined,
                }))
              }
              crossOrigin={undefined}
            />
            <Select
              label="통과 여부"
              value={
                filters.passed_only === undefined
                  ? ''
                  : filters.passed_only
                    ? 'true'
                    : 'false'
              }
              onChange={(value) =>
                setFilters((prev) => ({
                  ...prev,
                  passed_only: value === '' ? undefined : value === 'true',
                }))
              }
            >
              <Option value="">전체</Option>
              <Option value="true">통과만</Option>
              <Option value="false">실패만</Option>
            </Select>
          </div>
          <div className="mt-4 flex justify-end">
            <Button onClick={handleSearch} className="flex items-center gap-2">
              <MagnifyingGlassIcon className="h-4 w-4" />
              검색
            </Button>
          </div>
        </CardBody>
      </Card>

      {/* History List */}
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
                    <th className="border-b border-blue-gray-100 bg-blue-gray-50 p-4">RAGAS</th>
                    <th className="border-b border-blue-gray-100 bg-blue-gray-50 p-4">일시</th>
                  </tr>
                </thead>
                <tbody>
                  {data?.items.map((item) => (
                    <tr
                      key={item.history_id}
                      className="hover:bg-blue-gray-50 cursor-pointer"
                      onClick={() => fetchHistoryDetail(item.history_id)}
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
                              color="blue"
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
                          {item.question?.slice(0, 50)}...
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
                          F: {item.faithfulness?.toFixed(2) || '-'} / A:{' '}
                          {item.answer_relevancy?.toFixed(2) || '-'}
                        </Typography>
                      </td>
                      <td className="p-4 border-b border-blue-gray-50">
                        <Typography variant="small" color="blue-gray" className="font-normal">
                          {item.create_date
                            ? new Date(item.create_date).toLocaleString('ko-KR')
                            : '-'}
                        </Typography>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {/* Pagination */}
              {data && data.total_pages > 1 && (
                <div className="flex justify-center gap-2 mt-4 p-4">
                  <Button
                    variant="outlined"
                    size="sm"
                    disabled={data.page === 1}
                    onClick={() => handlePageChange(data.page - 1)}
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
                    onClick={() => handlePageChange(data.page + 1)}
                  >
                    다음
                  </Button>
                </div>
              )}
            </>
          )}
        </CardBody>
      </Card>

      {/* Detail Dialog */}
      <Dialog
        open={selectedHistory !== null}
        handler={() => setSelectedHistory(null)}
        size="xl"
      >
        <DialogHeader className="flex justify-between">
          <Typography variant="h5">
            상담 상세 #{selectedHistory?.history_id}
          </Typography>
          <XMarkIcon
            className="h-6 w-6 cursor-pointer"
            onClick={() => setSelectedHistory(null)}
          />
        </DialogHeader>
        <DialogBody divider className="max-h-[70vh] overflow-y-auto">
          {detailLoading ? (
            <div className="flex justify-center py-10">
              <Spinner className="h-8 w-8" />
            </div>
          ) : selectedHistory ? (
            <div className="space-y-6">
              {/* 기본 정보 */}
              <div>
                <Typography variant="h6" color="blue-gray" className="mb-2">
                  기본 정보
                </Typography>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-gray-500">사용자:</span>{' '}
                    {selectedHistory.username} ({selectedHistory.user_email})
                  </div>
                  <div>
                    <span className="text-gray-500">에이전트:</span>{' '}
                    {selectedHistory.agent_code || '-'}
                  </div>
                  <div>
                    <span className="text-gray-500">생성일:</span>{' '}
                    {selectedHistory.create_date
                      ? new Date(selectedHistory.create_date).toLocaleString('ko-KR')
                      : '-'}
                  </div>
                  <div>
                    <span className="text-gray-500">응답 시간:</span>{' '}
                    {selectedHistory.evaluation_data?.response_time?.toFixed(2) || '-'}초
                  </div>
                </div>
              </div>

              {/* 질문 */}
              <div>
                <Typography variant="h6" color="blue-gray" className="mb-2">
                  질문
                </Typography>
                <div className="bg-gray-100 p-4 rounded-lg whitespace-pre-wrap">
                  {selectedHistory.question}
                </div>
              </div>

              {/* 답변 */}
              <div>
                <Typography variant="h6" color="blue-gray" className="mb-2">
                  답변
                </Typography>
                <div className="bg-blue-50 p-4 rounded-lg whitespace-pre-wrap max-h-60 overflow-y-auto">
                  {selectedHistory.answer}
                </div>
              </div>

              {/* 평가 결과 */}
              {selectedHistory.evaluation_data && (
                <div>
                  <Typography variant="h6" color="blue-gray" className="mb-2">
                    평가 결과
                  </Typography>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <Card className="p-4 text-center">
                      <Typography variant="small" className="text-gray-500">
                        LLM 점수
                      </Typography>
                      <Typography variant="h5" color="blue">
                        {selectedHistory.evaluation_data.llm_score ?? '-'}/100
                      </Typography>
                      {selectedHistory.evaluation_data.llm_passed !== null && (
                        <Chip
                          value={selectedHistory.evaluation_data.llm_passed ? 'PASS' : 'FAIL'}
                          color={selectedHistory.evaluation_data.llm_passed ? 'green' : 'red'}
                          size="sm"
                          className="mt-2"
                        />
                      )}
                    </Card>
                    <Card className="p-4 text-center">
                      <Typography variant="small" className="text-gray-500">
                        Faithfulness
                      </Typography>
                      <Typography variant="h5" color="blue">
                        {selectedHistory.evaluation_data.faithfulness?.toFixed(2) ?? '-'}
                      </Typography>
                    </Card>
                    <Card className="p-4 text-center">
                      <Typography variant="small" className="text-gray-500">
                        Answer Relevancy
                      </Typography>
                      <Typography variant="h5" color="blue">
                        {selectedHistory.evaluation_data.answer_relevancy?.toFixed(2) ?? '-'}
                      </Typography>
                    </Card>
                    <Card className="p-4 text-center">
                      <Typography variant="small" className="text-gray-500">
                        Context Precision
                      </Typography>
                      <Typography variant="h5" color="blue">
                        {selectedHistory.evaluation_data.context_precision?.toFixed(2) ?? '-'}
                      </Typography>
                    </Card>
                  </div>
                </div>
              )}

              {/* 도메인 */}
              {selectedHistory.evaluation_data?.domains && (
                <div>
                  <Typography variant="h6" color="blue-gray" className="mb-2">
                    도메인
                  </Typography>
                  <div className="flex gap-2">
                    {selectedHistory.evaluation_data.domains.map((domain) => (
                      <Chip
                        key={domain}
                        value={DOMAIN_NAMES[domain] || domain}
                        color="blue"
                      />
                    ))}
                  </div>
                </div>
              )}

              {/* 검색된 문서 */}
              {selectedHistory.evaluation_data?.contexts &&
                selectedHistory.evaluation_data.contexts.length > 0 && (
                  <div>
                    <Typography variant="h6" color="blue-gray" className="mb-2">
                      검색된 문서 ({selectedHistory.evaluation_data.contexts.length}건)
                    </Typography>
                    <div className="space-y-2 max-h-60 overflow-y-auto">
                      {selectedHistory.evaluation_data.contexts.map((ctx, idx) => (
                        <div key={idx} className="bg-gray-50 p-3 rounded text-sm">
                          {ctx}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

              {/* 검색 평가 */}
              {selectedHistory.evaluation_data?.retrieval_evaluation && (
                <div>
                  <Typography variant="h6" color="blue-gray" className="mb-2">
                    검색 평가
                  </Typography>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div>
                      <span className="text-gray-500">상태:</span>{' '}
                      <Chip
                        value={selectedHistory.evaluation_data.retrieval_evaluation.status || '-'}
                        size="sm"
                        color={
                          selectedHistory.evaluation_data.retrieval_evaluation.status === 'PASS'
                            ? 'green'
                            : selectedHistory.evaluation_data.retrieval_evaluation.status === 'RETRY'
                              ? 'amber'
                              : 'red'
                        }
                      />
                    </div>
                    <div>
                      <span className="text-gray-500">문서 수:</span>{' '}
                      {selectedHistory.evaluation_data.retrieval_evaluation.doc_count ?? '-'}
                    </div>
                    <div>
                      <span className="text-gray-500">키워드 매칭:</span>{' '}
                      {selectedHistory.evaluation_data.retrieval_evaluation.keyword_match_ratio?.toFixed(
                        2
                      ) ?? '-'}
                    </div>
                    <div>
                      <span className="text-gray-500">평균 유사도:</span>{' '}
                      {selectedHistory.evaluation_data.retrieval_evaluation.avg_similarity?.toFixed(
                        2
                      ) ?? '-'}
                    </div>
                  </div>
                </div>
              )}
            </div>
          ) : null}
        </DialogBody>
        <DialogFooter>
          <Button variant="text" color="red" onClick={() => setSelectedHistory(null)}>
            닫기
          </Button>
        </DialogFooter>
      </Dialog>
    </div>
  );
};

const EvaluationStatsPanel: React.FC = () => {
  const [stats, setStats] = useState<AdminEvaluationStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchStats = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.get<AdminEvaluationStats>('/admin/histories/stats');
      setStats(response.data);
    } catch (err) {
      setError('통계를 불러오는데 실패했습니다.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
  }, []);

  if (loading) {
    return (
      <div className="flex justify-center py-10">
        <Spinner className="h-8 w-8" />
      </div>
    );
  }

  if (error) {
    return <div className="text-center py-10 text-red-500">{error}</div>;
  }

  if (!stats) {
    return null;
  }

  return (
    <div className="space-y-6">
      {/* 개요 카드 */}
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
    </div>
  );
};

export default AdminPage;
