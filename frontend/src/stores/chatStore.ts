import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { AgentCode, ChatMessage, ChatSession, SourceReference } from '../types';
import api from '../lib/api';
import { generateId } from '../lib/utils';
import { MAX_PARALLEL_CHAT_RESPONSES } from '../lib/constants';

const MAX_SESSIONS = 50;
const MAX_SERVER_HISTORY_LOAD = 100;
type ResponsePhase = 'loading' | 'streaming';

interface HistoryItem {
  history_id: number;
  agent_code: string;
  question: string;
  answer: string;
  create_date?: string;
  evaluation_data?: {
    sources?: Array<{ title: string; source: string; url: string; doc_download_url?: string; form_download_url?: string; form_s3_key?: string }>;
    [key: string]: unknown;
  } | null;
}

interface HistoryThreadSummary {
  root_history_id: number;
  last_history_id: number;
  title: string;
  message_count: number;
  first_create_date?: string;
  last_create_date?: string;
  source?: string;      // "db" | "redis"
  session_id?: string;  // Redis session ID
}

interface HistoryThreadDetail extends HistoryThreadSummary {
  histories: HistoryItem[];
}

const historyItemToMessages = (item: HistoryItem): ChatMessage[] => {
  if (!item.question || !item.answer) return [];
  const timestamp = item.create_date ? new Date(item.create_date) : new Date();
  const safeAgentCode: AgentCode = /^A\d{7}$/.test(item.agent_code)
    ? (item.agent_code as AgentCode)
    : 'A0000001';

  const rawSources = item.evaluation_data?.sources;
  const sources: SourceReference[] | undefined = rawSources?.length
    ? rawSources.map(s => ({
        title: s.title || '', source: s.source || '',
        url: s.url || '', docDownloadUrl: s.doc_download_url || '',
        formDownloadUrl: s.form_download_url || '',
        formS3Key: s.form_s3_key || '',
      }))
    : undefined;

  return [
    { id: generateId(), type: 'user', content: item.question, timestamp, synced: true },
    { id: generateId(), type: 'assistant', content: item.answer, agent_code: safeAgentCode,
      timestamp, synced: true, ...(sources ? { sources } : {}) },
  ];
};

interface ChatState {
  sessions: ChatSession[];
  currentSessionId: string | null;
  isLoading: boolean;
  isStreaming: boolean;
  responsePhaseBySessionId: Record<string, ResponsePhase>;
  isSyncing: boolean;
  isBootstrapping: boolean;
  guestMessageCount: number;
  authenticatedMessageCount: number;

  // Session management
  ensureCurrentSession: () => string;
  createSession: (title?: string) => string;
  switchSession: (sessionId: string) => void;
  deleteSession: (sessionId: string) => void;
  updateSessionTitle: (sessionId: string, title: string) => void;

  // Message management
  addMessage: (message: ChatMessage) => void;
  addMessageToSession: (sessionId: string, message: ChatMessage) => void;
  updateMessage: (messageId: string, updates: Partial<ChatMessage>) => void;
  setLoading: (loading: boolean) => void;
  setStreaming: (streaming: boolean) => void;
  clearMessages: () => void;

  // History linking (마지막 history_id 추적)
  setLastHistoryId: (id: number | null) => void;
  setLastHistoryIdForSession: (sessionId: string, id: number | null) => void;
  getLastHistoryId: () => number | null;

  // Session-aware message update (세션 기준 메시지 업데이트)
  updateMessageInSession: (sessionId: string, messageId: string, updates: Partial<ChatMessage>) => void;
  startSessionResponse: (sessionId: string) => void;
  markSessionStreaming: (sessionId: string) => void;
  finishSessionResponse: (sessionId: string) => void;
  isSessionResponding: (sessionId: string) => boolean;
  getRespondingSessionIds: () => string[];
  canStartNewResponse: (sessionId: string) => boolean;

  // Guest message limit
  incrementGuestCount: () => void;
  resetGuestCount: () => void;

  // Authenticated message quota
  incrementAuthenticatedCount: () => void;
  setAuthenticatedCount: (count: number) => void;

  // Guest -> Login sync
  syncGuestMessages: () => Promise<void>;
  bootstrapFromServerHistories: () => Promise<void>;

  // Logout cleanup
  resetOnLogout: () => void;

  // Getters
  getCurrentSession: () => ChatSession | undefined;
  getMessages: () => ChatMessage[];
}

const createNewSession = (title?: string): ChatSession => ({
  id: generateId(),
  title: title || '새 상담',
  messages: [],
  lastHistoryId: null,
  rootHistoryId: null,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
});

const toSessionTimestamp = (session: ChatSession): number => {
  const timestamp = new Date(session.updated_at).getTime();
  return Number.isFinite(timestamp) ? timestamp : 0;
};

const dedupeSessionsById = (sessions: ChatSession[]): ChatSession[] => {
  const byId = new Map<string, ChatSession>();

  sessions.forEach((session) => {
    const existing = byId.get(session.id);
    if (!existing) {
      byId.set(session.id, session);
      return;
    }

    const shouldReplace =
      toSessionTimestamp(session) > toSessionTimestamp(existing)
      || (
        toSessionTimestamp(session) === toSessionTimestamp(existing)
        && session.messages.length > existing.messages.length
      );

    if (shouldReplace) {
      byId.set(session.id, session);
    }
  });

  return Array.from(byId.values());
};

const appendMessageToSession = (session: ChatSession, message: ChatMessage): ChatSession => {
  // 새 메시지에 documentAttachment가 있으면 이전 문서 다운로드 비활성화
  let previousMessages = session.messages;
  if (message.documentAttachment) {
    previousMessages = session.messages.map((m) =>
      m.documentAttachment
        ? { ...m, documentAttachment: { ...m.documentAttachment, downloadable: false } }
        : m
    );
  }

  const updatedSession: ChatSession = {
    ...session,
    messages: [...previousMessages, message],
    updated_at: new Date().toISOString(),
  };

  // Auto-update title from first user message
  if (message.type === 'user' && session.messages.length === 0) {
    updatedSession.title = message.content.slice(0, 30) + (message.content.length > 30 ? '...' : '');
  }

  return updatedSession;
};

const hasAnyRespondingSession = (responsePhaseBySessionId: Record<string, ResponsePhase>): boolean =>
  Object.keys(responsePhaseBySessionId).length > 0;

const hasAnyStreamingSession = (responsePhaseBySessionId: Record<string, ResponsePhase>): boolean =>
  Object.values(responsePhaseBySessionId).some((phase) => phase === 'streaming');

export const useChatStore = create<ChatState>()(
  persist(
    (set, get) => ({
      sessions: [],
      currentSessionId: null,
      isLoading: false,
      isStreaming: false,
      responsePhaseBySessionId: {},
      isSyncing: false,
      isBootstrapping: false,
      guestMessageCount: 0,
      authenticatedMessageCount: 0,

      ensureCurrentSession: () => {
        const state = get();
        if (state.currentSessionId && state.sessions.some((s) => s.id === state.currentSessionId)) {
          return state.currentSessionId;
        }
        return state.createSession();
      },

      createSession: (title?: string) => {
        const session = createNewSession(title);
        set((state) => {
          // 세션은 최신순으로 앞에 추가하고 최대 개수만 유지
          const updated = [session, ...state.sessions];
          const trimmed = updated.length > MAX_SESSIONS
            ? updated.slice(0, MAX_SESSIONS)
            : updated;
          return {
            sessions: trimmed,
            currentSessionId: session.id,
          };
        });
        return session.id;
      },

      switchSession: (sessionId: string) => {
        set((state) => {
          const dedupedSessions = dedupeSessionsById(state.sessions);
          const nextCurrentSessionId = dedupedSessions.some((s) => s.id === sessionId)
            ? sessionId
            : (dedupedSessions[0]?.id ?? null);

          return {
            sessions: dedupedSessions,
            currentSessionId: nextCurrentSessionId,
          };
        });
      },

      deleteSession: (sessionId: string) => {
        set((state) => {
          const filtered = state.sessions.filter((s) => s.id !== sessionId);
          const newCurrentId =
            state.currentSessionId === sessionId
              ? filtered[0]?.id || null
              : state.currentSessionId;
          const { [sessionId]: _removed, ...nextResponsePhase } = state.responsePhaseBySessionId;
          return {
            sessions: filtered,
            currentSessionId: newCurrentId,
            responsePhaseBySessionId: nextResponsePhase,
            isLoading: hasAnyRespondingSession(nextResponsePhase),
            isStreaming: hasAnyStreamingSession(nextResponsePhase),
          };
        });
      },

      updateSessionTitle: (sessionId: string, title: string) => {
        set((state) => ({
          sessions: state.sessions.map((s) =>
            s.id === sessionId ? { ...s, title, updated_at: new Date().toISOString() } : s
          ),
        }));
      },

      addMessage: (message: ChatMessage) => {
        const sessionId = get().ensureCurrentSession();
        get().addMessageToSession(sessionId, message);
      },

      addMessageToSession: (sessionId: string, message: ChatMessage) => {
        if (!get().sessions.some((s) => s.id === sessionId)) return;

        set((prev) => ({
          sessions: prev.sessions.map((s) => {
            if (s.id !== sessionId) return s;
            return appendMessageToSession(s, message);
          }),
        }));
      },

      updateMessageInSession: (sessionId: string, messageId: string, updates: Partial<ChatMessage>) => {
        set((prev) => ({
          sessions: prev.sessions.map((s) => {
            if (s.id !== sessionId) return s;
            return {
              ...s,
              messages: s.messages.map((m) =>
                m.id === messageId ? { ...m, ...updates } : m
              ),
              updated_at: new Date().toISOString(),
            };
          }),
        }));
      },

      startSessionResponse: (sessionId: string) => {
        set((prev) => {
          if (!prev.sessions.some((s) => s.id === sessionId)) return prev;
          if (prev.responsePhaseBySessionId[sessionId]) return prev;

          const next = {
            ...prev.responsePhaseBySessionId,
            [sessionId]: 'loading' as const,
          };

          return {
            responsePhaseBySessionId: next,
            isLoading: hasAnyRespondingSession(next),
            isStreaming: hasAnyStreamingSession(next),
          };
        });
      },

      markSessionStreaming: (sessionId: string) => {
        set((prev) => {
          if (!prev.responsePhaseBySessionId[sessionId]) return prev;

          const next = {
            ...prev.responsePhaseBySessionId,
            [sessionId]: 'streaming' as const,
          };

          return {
            responsePhaseBySessionId: next,
            isLoading: hasAnyRespondingSession(next),
            isStreaming: hasAnyStreamingSession(next),
          };
        });
      },

      finishSessionResponse: (sessionId: string) => {
        set((prev) => {
          if (!prev.responsePhaseBySessionId[sessionId]) return prev;
          const { [sessionId]: _removed, ...next } = prev.responsePhaseBySessionId;

          return {
            responsePhaseBySessionId: next,
            isLoading: hasAnyRespondingSession(next),
            isStreaming: hasAnyStreamingSession(next),
          };
        });
      },

      isSessionResponding: (sessionId: string) => {
        return Boolean(get().responsePhaseBySessionId[sessionId]);
      },

      getRespondingSessionIds: () => {
        return Object.keys(get().responsePhaseBySessionId);
      },

      canStartNewResponse: (sessionId: string) => {
        const state = get();
        if (state.responsePhaseBySessionId[sessionId]) {
          return false;
        }
        return Object.keys(state.responsePhaseBySessionId).length < MAX_PARALLEL_CHAT_RESPONSES;
      },

      updateMessage: (messageId: string, updates: Partial<ChatMessage>) => {
        const sessionId = get().currentSessionId;
        if (!sessionId) return;
        get().updateMessageInSession(sessionId, messageId, updates);
      },

      setLoading: (loading: boolean) => set({ isLoading: loading }),

      setStreaming: (streaming: boolean) => set({ isStreaming: streaming }),

      clearMessages: () => {
        const state = get();
        if (!state.currentSessionId) return;
        set((prev) => ({
          sessions: prev.sessions.map((s) =>
            s.id === prev.currentSessionId ? { ...s, messages: [], updated_at: new Date().toISOString() } : s
          ),
        }));
      },

      setLastHistoryId: (id: number | null) => {
        const state = get();
        if (!state.currentSessionId) return;
        set((prev) => ({
          sessions: prev.sessions.map((s) =>
            s.id === prev.currentSessionId
              ? { ...s, lastHistoryId: id }
              : s
          ),
        }));
      },

      setLastHistoryIdForSession: (sessionId: string, id: number | null) => {
        set((prev) => ({
          sessions: prev.sessions.map((s) =>
            s.id === sessionId ? { ...s, lastHistoryId: id } : s
          ),
        }));
      },

      getLastHistoryId: () => {
        const state = get();
        const session = state.sessions.find((s) => s.id === state.currentSessionId);
        return session?.lastHistoryId ?? null;
      },

      incrementGuestCount: () =>
        set((state) => ({ guestMessageCount: state.guestMessageCount + 1 })),

      resetGuestCount: () => set({ guestMessageCount: 0 }),

      incrementAuthenticatedCount: () =>
        set((state) => ({ authenticatedMessageCount: state.authenticatedMessageCount + 1 })),

      setAuthenticatedCount: (count: number) => set({ authenticatedMessageCount: count }),

      syncGuestMessages: async () => {
        if (get().isSyncing) return;
        set({ isSyncing: true });

        try {
          const state = get();
          const candidateSessions = state.sessions.filter((s) => s.messages.length > 0);
          if (!candidateSessions.length) return;

          for (const session of candidateSessions) {
            const messages = session.messages;
            const sessionId = session.id;
            // rootHistoryId: 이 세션의 첫 번째 메시지 history_id (모든 후속 메시지가 참조)
            let rootHistoryId: number | null = session.rootHistoryId ?? null;

            for (let i = 0; i < messages.length; i++) {
              const msg = messages[i];
              if (msg.type !== 'user' || msg.synced) continue;

              const assistantMsg = messages[i + 1];
              if (!assistantMsg || assistantMsg.type !== 'assistant') continue;

              try {
                const evalData: Record<string, unknown> = { ...(assistantMsg.evaluation_data || {}) };
                if (assistantMsg.sources?.length) {
                  evalData.sources = assistantMsg.sources.map(s => ({
                    title: s.title, source: s.source, url: s.url,
                    doc_download_url: s.docDownloadUrl || '',
                    form_download_url: s.formDownloadUrl || '',
                    form_s3_key: s.formS3Key || '',
                  }));
                }
                const res: { data: { history_id: number } } = await api.post('/histories', {
                  agent_code: assistantMsg.agent_code || 'A0000001',
                  question: msg.content,
                  answer: assistantMsg.content,
                  parent_history_id: rootHistoryId,
                  ...(Object.keys(evalData).length > 0 ? { evaluation_data: evalData } : {}),
                });
                const newHistoryId = res.data.history_id;
                // 첫 번째 저장된 메시지의 history_id가 이 세션의 root
                if (rootHistoryId === null) {
                  rootHistoryId = newHistoryId;
                }

                set((prev) => ({
                  sessions: prev.sessions.map((s) =>
                    s.id === sessionId
                      ? {
                          ...s,
                          lastHistoryId: newHistoryId,
                          rootHistoryId,
                          messages: s.messages.map((m) =>
                            m.id === msg.id || m.id === assistantMsg.id
                              ? { ...m, synced: true }
                              : m
                          ),
                          updated_at: new Date().toISOString(),
                        }
                      : s
                  ),
                }));
              } catch {
                // Keep unsynced messages for retry.
              }
            }
          }

          // 개별 메시지별 synced 마킹은 위 try 블록에서 성공 시에만 처리됨
          // 실패한 메시지는 synced=false 유지 → 다음 로그인 시 재시도
        } finally {
          set({ isSyncing: false });
        }
      },
      bootstrapFromServerHistories: async () => {
        if (get().isBootstrapping) return;
        set({ isBootstrapping: true });

        try {
          const state = get();
          const response = await api.get<HistoryThreadSummary[]>('/histories/threads', {
            params: { limit: MAX_SERVER_HISTORY_LOAD, offset: 0 },
          });
          const threads = response.data ?? [];
          if (threads.length === 0) return;

          // Redis 세션과 DB 세션을 분리
          const dbThreads = threads.filter(t => t.source !== 'redis');
          const redisThreads = threads.filter(t => t.source === 'redis');

          // DB 세션: 기존 방식으로 상세 조회
          const details = await Promise.all(
            dbThreads.map(async (thread) => {
              try {
                const detailResponse = await api.get<HistoryThreadDetail>(
                  `/histories/threads/${thread.root_history_id}`
                );
                return detailResponse.data;
              } catch {
                return null;
              }
            })
          );

          const fetchedSessions: ChatSession[] = [];

          // DB 세션 변환
          for (const detail of details) {
            if (!detail || !detail.histories.length) continue;

            const sorted = [...detail.histories].sort((a, b) => {
              const aTime = a.create_date ? new Date(a.create_date).getTime() : 0;
              const bTime = b.create_date ? new Date(b.create_date).getTime() : 0;
              return aTime - bTime;
            });

            const messages = sorted.flatMap(historyItemToMessages);

            if (!messages.length) continue;

            const createdAt = detail.first_create_date ?? new Date().toISOString();
            const updatedAt = detail.last_create_date ?? createdAt;
            fetchedSessions.push({
              id: `db-${detail.root_history_id}`,
              title: detail.title || '기존 상담 내역',
              messages,
              lastHistoryId: detail.last_history_id,
              rootHistoryId: detail.root_history_id,
              created_at: createdAt,
              updated_at: updatedAt,
            });
          }

          // Redis 활성 세션 변환 (상세 조회 + session_id를 프론트엔드 세션 ID로 매핑)
          await Promise.all(redisThreads.map(async (redisThread) => {
            try {
              const detailResp = await api.get<HistoryThreadDetail>(
                `/histories/threads/${redisThread.root_history_id}`,
                { params: { session_id: redisThread.session_id } }
              );
              const detail = detailResp.data;
              if (!detail || !detail.histories.length) return;

              const messages = detail.histories.flatMap(historyItemToMessages);
              if (!messages.length) return;

              // Redis 세션: session_id를 프론트엔드 세션 ID로 사용하여 채팅 연결
              const sessionId = redisThread.session_id || generateId();
              const createdAt = detail.first_create_date ?? new Date().toISOString();
              const updatedAt = detail.last_create_date ?? createdAt;
              fetchedSessions.push({
                id: sessionId,
                title: detail.title || '활성 상담',
                messages,
                lastHistoryId: null,  // Redis 세션은 아직 DB에 없음
                rootHistoryId: null,
                created_at: createdAt,
                updated_at: updatedAt,
              });
            } catch {
              // Redis session detail fetch failure is non-critical
            }
          }));

          if (!fetchedSessions.length) return;

          const existingSessions = state.sessions;
          const existingHistoryIds = new Set(
            existingSessions
              .map((s) => s.lastHistoryId)
              .filter((id): id is number => typeof id === 'number')
          );

          const mergedSessions = dedupeSessionsById([
            ...existingSessions,
            ...fetchedSessions.filter((s) => {
              if (!s.lastHistoryId) return true;
              return !existingHistoryIds.has(s.lastHistoryId);
            }),
          ]);

          mergedSessions.sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime());
          const currentExists = mergedSessions.some((s) => s.id === state.currentSessionId);

          set({
            sessions: mergedSessions.slice(0, MAX_SESSIONS),
            currentSessionId: currentExists ? state.currentSessionId : (mergedSessions[0]?.id ?? null),
          });
        } catch {
          // History bootstrap failure is non-critical
        } finally {
          set({ isBootstrapping: false });
        }
      },
      resetOnLogout: () => {
        const newSession = createNewSession();
        set({
          sessions: [newSession],
          currentSessionId: newSession.id,
          responsePhaseBySessionId: {},
          isLoading: false,
          isStreaming: false,
          // guestMessageCount는 유지 (로그아웃→게스트→로그인 순환 악용 방지)
          authenticatedMessageCount: 0,
        });
      },

      getCurrentSession: () => {
        const state = get();
        return state.sessions.find((s) => s.id === state.currentSessionId);
      },

      getMessages: () => {
        return get().getCurrentSession()?.messages || [];
      },
    }),
    {
      name: 'chat-storage',
      partialize: (state) => ({
        sessions: state.sessions,
        currentSessionId: state.currentSessionId,
        guestMessageCount: state.guestMessageCount,
      }),
      merge: (persistedState, currentState) => {
        const typedPersisted = (persistedState as Partial<ChatState> | undefined) ?? {};
        const persistedSessions = Array.isArray(typedPersisted.sessions)
          ? dedupeSessionsById(typedPersisted.sessions as ChatSession[])
          : currentState.sessions;
        const persistedCurrentSessionId =
          typeof typedPersisted.currentSessionId === 'string'
            ? typedPersisted.currentSessionId
            : null;
        const currentSessionId = persistedCurrentSessionId
          && persistedSessions.some((session) => session.id === persistedCurrentSessionId)
          ? persistedCurrentSessionId
          : (persistedSessions[0]?.id ?? null);

        return {
          ...currentState,
          ...typedPersisted,
          sessions: persistedSessions,
          currentSessionId,
        };
      },
    }
  )
);



