import React from 'react';
import {
  Card,
  Typography,
  Button,
  Chip,
  Spinner,
} from '@material-tailwind/react';
import ReactMarkdown from 'react-markdown';
import { Modal } from '../common/Modal';
import remarkGfm from 'remark-gfm';
import type { AdminHistoryDetail } from '../../types';
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

const scoreColor = (score: number | null): 'green' | 'amber' | 'red' | 'blue' => {
  if (score === null) return 'blue';
  if (score >= 0.7) return 'green';
  if (score >= 0.4) return 'amber';
  return 'red';
};

interface HistoryDetailModalProps {
  history: AdminHistoryDetail | null;
  loading: boolean;
  onClose: () => void;
}

export const HistoryDetailModal: React.FC<HistoryDetailModalProps> = ({
  history,
  loading,
  onClose,
}) => {
  return (
    <Modal
      open={history !== null}
      onClose={onClose}
      title={`상담 상세 #${history?.history_id ?? ''}`}
      size="xl"
      footer={
        <div className="flex justify-end">
          <Button variant="text" color="red" onClick={onClose}>
            닫기
          </Button>
        </div>
      }
    >
      <div className="text-gray-900">
        {loading ? (
          <div className="flex justify-center py-10">
            <Spinner className="h-8 w-8" />
          </div>
        ) : history ? (
          <div className="space-y-6">
            {/* 기본 정보 */}
            <div>
              <Typography variant="h6" color="blue-gray" className="mb-2 !text-gray-900">
                기본 정보
              </Typography>
              <div className="grid grid-cols-2 gap-4 text-sm text-gray-900">
                <div>
                  <span className="text-gray-600">사용자:</span>{' '}
                  {history.username} ({history.user_email})
                </div>
                <div>
                  <span className="text-gray-600">에이전트:</span>{' '}
                  {history.agent_name || history.agent_code || '-'}
                </div>
                <div>
                  <span className="text-gray-600">생성일:</span>{' '}
                  {history.create_date
                    ? formatDateTime(history.create_date)
                    : '-'}
                </div>
                <div>
                  <span className="text-gray-600">응답 시간:</span>{' '}
                  {history.evaluation_data?.response_time?.toFixed(2) || '-'}초
                </div>
              </div>
            </div>

            {/* 질문 */}
            <div>
              <Typography variant="h6" color="blue-gray" className="mb-2 !text-gray-900">
                질문
              </Typography>
              <div className="bg-gray-100 p-4 rounded-lg whitespace-pre-wrap text-gray-900 break-words">
                {history.question}
              </div>
            </div>

            {/* 답변 (Markdown 렌더링) */}
            <div>
              <Typography variant="h6" color="blue-gray" className="mb-2 !text-gray-900">
                답변
              </Typography>
              <div className="bg-blue-50 p-4 rounded-lg markdown-body text-gray-900 break-words overflow-hidden">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {history.answer || ''}
                </ReactMarkdown>
              </div>
            </div>

            {/* LLM 평가 */}
            {history.evaluation_data && (
              <div>
                <Typography variant="h6" color="blue-gray" className="mb-2 !text-gray-900">
                  LLM 평가
                </Typography>
                <Card className="p-4">
                  <div className="flex items-center gap-4">
                    <Typography variant="h4" color="blue">
                      {history.evaluation_data.llm_score ?? '-'}/100
                    </Typography>
                    {history.evaluation_data.llm_passed !== null && (
                      <Chip
                        value={history.evaluation_data.llm_passed ? 'PASS' : 'FAIL'}
                        color={history.evaluation_data.llm_passed ? 'green' : 'red'}
                        size="sm"
                      />
                    )}
                  </div>
                </Card>
              </div>
            )}

            {/* RAGAS 평가 */}
            {history.evaluation_data && (
              <div>
                <Typography variant="h6" color="blue-gray" className="mb-2 !text-gray-900">
                  RAGAS 평가
                </Typography>
                <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                  {([
                    { label: 'Faithfulness', value: history.evaluation_data.faithfulness },
                    { label: 'Answer Relevancy', value: history.evaluation_data.answer_relevancy },
                    { label: 'Context Precision', value: history.evaluation_data.context_precision },
                    { label: 'Context Recall', value: history.evaluation_data.context_recall },
                    {
                      label: 'F1-Score',
                      value: calcF1(
                        history.evaluation_data.context_precision,
                        history.evaluation_data.context_recall,
                      ),
                    },
                  ] as { label: string; value: number | null }[]).map(({ label, value }) => (
                    <Card key={label} className="p-4 text-center">
                      <Typography variant="small" className="text-gray-600">
                        {label}
                      </Typography>
                      <Typography variant="h5" color={scoreColor(value)}>
                        {value !== null && value !== undefined ? value.toFixed(2) : 'N/A'}
                      </Typography>
                    </Card>
                  ))}
                </div>
              </div>
            )}

            {/* 도메인 */}
            {history.evaluation_data?.domains &&
              history.evaluation_data.domains.length > 0 && (
              <div>
                <Typography variant="h6" color="blue-gray" className="mb-2 !text-gray-900">
                  도메인
                </Typography>
                <div className="flex gap-2">
                  {history.evaluation_data.domains.map((domain) => (
                    <Chip
                      key={domain}
                      value={DOMAIN_NAMES[domain] || domain}
                      color={DOMAIN_CHIP_COLORS[domain] || 'blue'}
                    />
                  ))}
                </div>
              </div>
            )}

            {/* 검색된 문서 */}
            {history.evaluation_data?.contexts &&
              history.evaluation_data.contexts.length > 0 && (
                <div>
                  <Typography variant="h6" color="blue-gray" className="mb-2 !text-gray-900">
                    검색된 문서 ({history.evaluation_data.contexts.length}건)
                  </Typography>
                  <div className="space-y-2">
                    {history.evaluation_data.contexts.map((ctx, idx) => (
                      <div key={idx} className="bg-gray-50 p-3 rounded text-sm text-gray-900 break-words">
                        {ctx}
                      </div>
                    ))}
                  </div>
                </div>
              )}

            {/* 검색 평가 */}
            {history.evaluation_data?.retrieval_evaluation && (
              <div>
                <Typography variant="h6" color="blue-gray" className="mb-2 !text-gray-900">
                  검색 평가
                </Typography>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm text-gray-900">
                  <div>
                    <span className="text-gray-600">상태:</span>{' '}
                    <Chip
                      value={history.evaluation_data.retrieval_evaluation.status || '-'}
                      size="sm"
                      color={
                        history.evaluation_data.retrieval_evaluation.status === 'PASS'
                          ? 'green'
                          : history.evaluation_data.retrieval_evaluation.status === 'RETRY'
                            ? 'amber'
                            : 'red'
                      }
                    />
                  </div>
                  <div>
                    <span className="text-gray-600">문서 수:</span>{' '}
                    {history.evaluation_data.retrieval_evaluation.doc_count ?? '-'}
                  </div>
                  <div>
                    <span className="text-gray-600">키워드 매칭:</span>{' '}
                    {history.evaluation_data.retrieval_evaluation.keyword_match_ratio?.toFixed(
                      2
                    ) ?? '-'}
                  </div>
                  <div>
                    <span className="text-gray-600">평균 유사도:</span>{' '}
                    {history.evaluation_data.retrieval_evaluation.avg_similarity?.toFixed(
                      2
                    ) ?? '-'}
                  </div>
                </div>
              </div>
            )}
          </div>
        ) : null}
      </div>
    </Modal>
  );
};
