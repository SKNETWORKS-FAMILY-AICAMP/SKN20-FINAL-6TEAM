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
export type AgentCode = 'A0000001' | 'A0000002' | 'A0000003' | 'A0000004' | 'A0000005' | 'A0000006';

export const AGENT_NAMES: Record<AgentCode, string> = {
  A0000001: '메인',
  A0000002: '창업·지원',
  A0000003: '재무·세무',
  A0000004: '인사·노무',
  A0000005: '평가·검증',
  A0000006: '마케팅',
};

export const AGENT_COLORS: Record<AgentCode, string> = {
  A0000001: 'bg-blue-500',
  A0000002: 'bg-green-500',
  A0000003: 'bg-purple-500',
  A0000004: 'bg-orange-500',
  A0000005: 'bg-cyan-500',
  A0000006: 'bg-pink-500',
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

// RAG Chat Response
export interface RagChatResponse {
  response: string;
  agent_code: AgentCode;
}

// Calendar Event (for FullCalendar)
export interface CalendarEvent {
  id: string;
  title: string;
  start: string;
  end: string;
  backgroundColor?: string;
  borderColor?: string;
  extendedProps?: {
    schedule_id: number;
    company_id: number;
    memo?: string;
  };
}

// API Response
export interface ApiResponse<T> {
  data: T;
  message?: string;
}

// Auth
export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
}
