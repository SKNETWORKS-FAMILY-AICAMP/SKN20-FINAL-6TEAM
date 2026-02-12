// User types
export interface User {
  user_id: number;
  google_email: string;
  username: string;
  type_code: 'U0000001' | 'U0000002' | 'U0000003'; // U0000001: 관리자, U0000002: 예비창업자, U0000003: 사업자
  birth?: string;
  create_date?: string;
}

// Company types
export interface Company {
  company_id: number;
  user_id: number;
  com_name: string;
  biz_num: string;
  addr: string;
  open_date?: string;
  biz_code?: string;
  file_path: string;
  main_yn: boolean;
  create_date?: string;
}

// History types
export interface History {
  history_id: number;
  user_id: number;
  agent_code: AgentCode;
  question: string;
  answer: string;
  parent_history_id?: number;
  create_date?: string;
}

// Schedule types
export interface Schedule {
  schedule_id: number;
  company_id: number;
  announce_id?: number;
  schedule_name: string;
  start_date: string;
  end_date: string;
  memo?: string;
  create_date?: string;
}

// Agent codes
export type AgentCode = 'A0000001' | 'A0000002' | 'A0000003' | 'A0000004' | 'A0000005' | 'A0000006' | 'A0000007';

export const AGENT_NAMES: Record<AgentCode, string> = {
  A0000001: '메인',
  A0000002: '창업·지원',
  A0000003: '재무·세무',
  A0000004: '인사·노무',
  A0000005: '평가·검증',
  A0000006: '마케팅',
  A0000007: '법률',
};

export const AGENT_COLORS: Record<AgentCode, string> = {
  A0000001: 'bg-blue-500',
  A0000002: 'bg-green-500',
  A0000003: 'bg-purple-500',
  A0000004: 'bg-orange-500',
  A0000005: 'bg-cyan-500',
  A0000006: 'bg-pink-500',
  A0000007: 'bg-red-500',
};

// User type codes
export const USER_TYPE_NAMES: Record<string, string> = {
  U0000001: '관리자',
  U0000002: '예비창업자',
  U0000003: '사업자',
};

// Chat message
export interface ChatMessage {
  id: string;
  type: 'user' | 'assistant';
  content: string;
  agent_code?: AgentCode;
  agent_codes?: AgentCode[];
  timestamp: Date;
}

// Chat session
export interface ChatSession {
  id: string;
  title: string;
  messages: ChatMessage[];
  created_at: string;
  updated_at: string;
}

// Notification
export interface Notification {
  id: string;
  title: string;
  message: string;
  type: 'schedule' | 'info' | 'warning';
  is_read: boolean;
  created_at: string;
  link?: string;
}

// RAG Chat Response (matches rag/schemas/response.py ChatResponse)
export interface RagChatResponse {
  content: string;
  domain: string;
  domains: string[];
  sources: RagSourceDocument[];
  actions: RagActionSuggestion[];
  evaluation: RagEvaluationResult | null;
  session_id: string | null;
  retry_count: number;
  ragas_metrics: Record<string, unknown> | null;
}

// RAG Streaming Response (SSE events)
export interface RagStreamResponse {
  type: 'token' | 'source' | 'action' | 'done' | 'error';
  content?: string;
  metadata?: {
    index?: number;
    title?: string;
    source?: string;
    type?: string;
    params?: Record<string, unknown>;
    domain?: string;
    domains?: string[];
    response_time?: number;
  };
}

export interface RagSourceDocument {
  title: string | null;
  content: string;
  source: string | null;
  metadata: Record<string, unknown>;
}

export interface RagActionSuggestion {
  type: string;
  label: string;
  description: string | null;
  params: Record<string, unknown>;
}

export interface RagEvaluationResult {
  scores: Record<string, number>;
  total_score: number;
  passed: boolean;
  feedback: string | null;
}

// Admin types
export interface RetrievalEvaluationData {
  status: string | null;
  doc_count: number | null;
  keyword_match_ratio: number | null;
  avg_similarity: number | null;
  used_multi_query: boolean;
}

export interface EvaluationData {
  faithfulness: number | null;
  answer_relevancy: number | null;
  context_precision: number | null;
  llm_score: number | null;
  llm_passed: boolean | null;
  contexts: string[];
  domains: string[];
  retrieval_evaluation: RetrievalEvaluationData | null;
  response_time: number | null;
}

export interface AdminHistoryListItem {
  history_id: number;
  user_id: number;
  agent_code: string | null;
  question: string | null;
  answer_preview: string | null;
  create_date: string | null;
  faithfulness: number | null;
  answer_relevancy: number | null;
  llm_score: number | null;
  llm_passed: boolean | null;
  domains: string[];
  user_email: string | null;
  username: string | null;
}

export interface AdminHistoryListResponse {
  items: AdminHistoryListItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface AdminHistoryDetail {
  history_id: number;
  user_id: number;
  agent_code: string | null;
  question: string | null;
  answer: string | null;
  parent_history_id: number | null;
  evaluation_data: EvaluationData | null;
  create_date: string | null;
  update_date: string | null;
  user_email: string | null;
  username: string | null;
}

export interface AdminEvaluationStats {
  total_count: number;
  evaluated_count: number;
  passed_count: number;
  failed_count: number;
  avg_faithfulness: number | null;
  avg_answer_relevancy: number | null;
  avg_llm_score: number | null;
  domain_counts: Record<string, number>;
}

export interface AdminHistoryFilters {
  page?: number;
  page_size?: number;
  start_date?: string;
  end_date?: string;
  domain?: string;
  agent_code?: string;
  min_score?: number;
  max_score?: number;
  passed_only?: boolean;
  user_id?: number;
}

// Server status types
export interface ServiceStatus {
  name: string;
  status: 'healthy' | 'degraded' | 'unhealthy';
  response_time_ms: number | null;
  details: Record<string, unknown>;
}

export interface ServerStatusResponse {
  overall_status: 'healthy' | 'degraded' | 'unhealthy';
  services: ServiceStatus[];
  uptime_seconds: number;
  checked_at: string;
}

// Domain names for display
export const DOMAIN_NAMES: Record<string, string> = {
  startup_funding: '창업/지원',
  finance_tax: '재무/세무',
  hr_labor: '인사/노무',
  law_common: '법률',
  general: '일반',
};
