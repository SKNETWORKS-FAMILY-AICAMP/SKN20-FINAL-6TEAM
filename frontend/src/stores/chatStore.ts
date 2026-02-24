import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { AgentCode, ChatMessage, ChatSession } from '../types';
import api from '../lib/api';
import { generateId } from '../lib/utils';

const MAX_SESSIONS = 50;
const MAX_SERVER_HISTORY_LOAD = 100;

// syncGuestMessages ??덈뻻 ?紐꾪뀱 獄쎻뫗? 揶쎛??
let isSyncing = false;
let isBootstrapping = false;

interface HistoryItem {
  history_id: number;
  agent_code: string;
  question: string;
  answer: string;
  create_date?: string;
}

interface HistoryThreadSummary {
  root_history_id: number;
  last_history_id: number;
  title: string;
  message_count: number;
  first_create_date?: string;
  last_create_date?: string;
}

interface HistoryThreadDetail extends HistoryThreadSummary {
  histories: HistoryItem[];
}

interface ChatState {
  sessions: ChatSession[];
  currentSessionId: string | null;
  isLoading: boolean;
  isStreaming: boolean;
  guestMessageCount: number;

  // Session management
  createSession: (title?: string) => string;
  switchSession: (sessionId: string) => void;
  deleteSession: (sessionId: string) => void;
  updateSessionTitle: (sessionId: string, title: string) => void;

  // Message management
  addMessage: (message: ChatMessage) => void;
  updateMessage: (messageId: string, updates: Partial<ChatMessage>) => void;
  setLoading: (loading: boolean) => void;
  setStreaming: (streaming: boolean) => void;
  clearMessages: () => void;

  // History linking (?紐꾨↑퉪?
  setLastHistoryId: (id: number | null) => void;
  setLastHistoryIdForSession: (sessionId: string, id: number | null) => void;
  getLastHistoryId: () => number | null;

  // Session-aware message update (??쑬猷욄묾?餓??紐꾨??袁れ넎 ????
  updateMessageInSession: (sessionId: string, messageId: string, updates: Partial<ChatMessage>) => void;

  // Guest message limit
  incrementGuestCount: () => void;
  resetGuestCount: () => void;

  // Guest ??Login sync
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
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
});

export const useChatStore = create<ChatState>()(
  persist(
    (set, get) => ({
      sessions: [],
      currentSessionId: null,
      isLoading: false,
      isStreaming: false,
      guestMessageCount: 0,

      createSession: (title?: string) => {
        const session = createNewSession(title);
        set((state) => {
          // ??살삋???紐꾨??癒?짗 ?類ｂ봺 (MAX_SESSIONS ?λ뜃????
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
        set({ currentSessionId: sessionId });
      },

      deleteSession: (sessionId: string) => {
        set((state) => {
          const filtered = state.sessions.filter((s) => s.id !== sessionId);
          const newCurrentId =
            state.currentSessionId === sessionId
              ? filtered[0]?.id || null
              : state.currentSessionId;
          return {
            sessions: filtered,
            currentSessionId: newCurrentId,
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
        const state = get();
        let sessionId = state.currentSessionId;

        // Auto-create session if none exists
        if (!sessionId || !state.sessions.find((s) => s.id === sessionId)) {
          const session = createNewSession();
          set((prev) => ({
            sessions: [session, ...prev.sessions],
            currentSessionId: session.id,
          }));
          sessionId = session.id;
        }

        set((prev) => ({
          sessions: prev.sessions.map((s) => {
            if (s.id !== sessionId) return s;
            const updated = {
              ...s,
              messages: [...s.messages, message],
              updated_at: new Date().toISOString(),
            };
            // Auto-update title from first user message
            if (message.type === 'user' && s.messages.length === 0) {
              updated.title = message.content.slice(0, 30) + (message.content.length > 30 ? '...' : '');
            }
            return updated;
          }),
        }));
      },

      updateMessage: (messageId: string, updates: Partial<ChatMessage>) => {
        const state = get();
        const sessionId = state.currentSessionId;
        if (!sessionId) return;

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

      syncGuestMessages: async () => {
        if (isSyncing) return;
        isSyncing = true;

        try {
          const state = get();
          const candidateSessions = state.sessions.filter((s) => s.messages.length > 0);
          if (!candidateSessions.length) return;

          for (const session of candidateSessions) {
            const messages = session.messages;
            const sessionId = session.id;
            let lastSyncedHistoryId: number | null = session.lastHistoryId ?? null;

            for (let i = 0; i < messages.length; i++) {
              const msg = messages[i];
              if (msg.type !== 'user' || msg.synced) continue;

              const assistantMsg = messages[i + 1];
              if (!assistantMsg || assistantMsg.type !== 'assistant') continue;

              try {
                const res: { data: { history_id: number } } = await api.post('/histories', {
                  agent_code: assistantMsg.agent_code || 'A0000001',
                  question: msg.content,
                  answer: assistantMsg.content,
                  parent_history_id: lastSyncedHistoryId,
                });
                lastSyncedHistoryId = res.data.history_id;

                set((prev) => ({
                  sessions: prev.sessions.map((s) =>
                    s.id === sessionId
                      ? {
                          ...s,
                          lastHistoryId: lastSyncedHistoryId,
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

          // 기존 세션의 모든 메시지를 synced로 마킹 (재로그인 시 중복 방지)
          // 새 세션을 생성하지 않고 현재 세션 유지 → 채팅 내역 그대로 표시
          set((prev) => ({
            sessions: prev.sessions.map((s) =>
              s.id === sessionId
                ? { ...s, messages: s.messages.map((m) => ({ ...m, synced: true })) }
                : s
            ),
          }));
        } finally {
          isSyncing = false;
        }
      },
      bootstrapFromServerHistories: async () => {
        if (isBootstrapping) return;
        isBootstrapping = true;

        try {
          const state = get();
          const response = await api.get<HistoryThreadSummary[]>('/histories/threads', {
            params: { limit: MAX_SERVER_HISTORY_LOAD, offset: 0 },
          });
          const threads = response.data ?? [];
          if (threads.length === 0) return;

          const details = await Promise.all(
            threads.map(async (thread) => {
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
          for (const detail of details) {
            if (!detail || !detail.histories.length) continue;

            const sorted = [...detail.histories].sort((a, b) => {
              const aTime = a.create_date ? new Date(a.create_date).getTime() : 0;
              const bTime = b.create_date ? new Date(b.create_date).getTime() : 0;
              return aTime - bTime;
            });

            const messages: ChatMessage[] = [];
            for (const item of sorted) {
              if (!item.question || !item.answer) continue;

              const timestamp = item.create_date ? new Date(item.create_date) : new Date();
              const safeAgentCode: AgentCode = /^A\d{7}$/.test(item.agent_code)
                ? (item.agent_code as AgentCode)
                : 'A0000001';

              messages.push({
                id: generateId(),
                type: 'user',
                content: item.question,
                timestamp,
                synced: true,
              });
              messages.push({
                id: generateId(),
                type: 'assistant',
                content: item.answer,
                agent_code: safeAgentCode,
                timestamp,
                synced: true,
              });
            }

            if (!messages.length) continue;

            const createdAt = detail.first_create_date ?? new Date().toISOString();
            const updatedAt = detail.last_create_date ?? createdAt;
            fetchedSessions.push({
              id: generateId(),
              title: detail.title || '기존 상담 내역',
              messages,
              lastHistoryId: detail.last_history_id,
              created_at: createdAt,
              updated_at: updatedAt,
            });
          }

          if (!fetchedSessions.length) return;

          const existingSessions = state.sessions;
          const existingHistoryIds = new Set(
            existingSessions
              .map((s) => s.lastHistoryId)
              .filter((id): id is number => typeof id === 'number')
          );

          const mergedSessions = [
            ...existingSessions,
            ...fetchedSessions.filter((s) => {
              if (!s.lastHistoryId) return true;
              return !existingHistoryIds.has(s.lastHistoryId);
            }),
          ];

          mergedSessions.sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime());
          const currentExists = mergedSessions.some((s) => s.id === state.currentSessionId);

          set({
            sessions: mergedSessions.slice(0, MAX_SESSIONS),
            currentSessionId: currentExists ? state.currentSessionId : (mergedSessions[0]?.id ?? null),
          });
        } catch {
          // History bootstrap failure is non-critical
        } finally {
          isBootstrapping = false;
        }
      },
      resetOnLogout: () => {
        const newSession = createNewSession();
        set({
          sessions: [newSession],
          currentSessionId: newSession.id,
          guestMessageCount: 0,
        });
      },

      getCurrentSession: () => {
        const state = get();
        return state.sessions.find((s) => s.id === state.currentSessionId);
      },

      getMessages: () => {
        const state = get();
        const session = state.sessions.find((s) => s.id === state.currentSessionId);
        return session?.messages || [];
      },
    }),
    {
      name: 'chat-storage',
      partialize: (state) => ({
        sessions: state.sessions,
        currentSessionId: state.currentSessionId,
        guestMessageCount: state.guestMessageCount,
      }),
    }
  )
);



