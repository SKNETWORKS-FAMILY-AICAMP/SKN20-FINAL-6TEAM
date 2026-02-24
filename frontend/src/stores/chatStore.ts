import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { ChatMessage, ChatSession } from '../types';
import api from '../lib/api';
import { generateId } from '../lib/utils';

const MAX_SESSIONS = 50;

// syncGuestMessages 동시 호출 방지 가드
let isSyncing = false;

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

  // History linking (세션별)
  setLastHistoryId: (id: number | null) => void;
  setLastHistoryIdForSession: (sessionId: string, id: number | null) => void;
  getLastHistoryId: () => number | null;

  // Session-aware message update (비동기 중 세션 전환 대응)
  updateMessageInSession: (sessionId: string, messageId: string, updates: Partial<ChatMessage>) => void;

  // Guest message limit
  incrementGuestCount: () => void;
  resetGuestCount: () => void;

  // Guest → Login sync
  syncGuestMessages: () => Promise<void>;

  // Logout cleanup
  resetOnLogout: () => void;

  // Getters
  getCurrentSession: () => ChatSession | undefined;
  getMessages: () => ChatMessage[];
}

const createNewSession = (title?: string): ChatSession => ({
  id: generateId(),
  title: title || '새 채팅',
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
          // 오래된 세션 자동 정리 (MAX_SESSIONS 초과 시)
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
        // 동시 호출 방지 (login이 빠르게 2번 호출되는 경우 대응)
        if (isSyncing) return;
        isSyncing = true;

        try {
          const state = get();
          const session = state.sessions.find((s) => s.id === state.currentSessionId);
          if (!session || session.messages.length === 0) return;

          const messages = session.messages;
          const sessionId = session.id; // 세션 ID 고정
          // 기존 lastHistoryId를 시작점으로 사용 (parent chain 유지)
          let lastSyncedHistoryId: number | null = session.lastHistoryId ?? null;
          let anySynced = false;

          for (let i = 0; i < messages.length; i++) {
            const msg = messages[i];
            if (msg.type !== 'user') continue;
            if (msg.synced) continue;

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
              anySynced = true;

              // 메시지별 즉시 synced 마킹 (부분 실패 시에도 성공분은 보존)
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
              // 개별 실패는 건너뜀 — 이미 성공한 것은 마킹됨
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
