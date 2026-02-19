import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { ChatMessage, ChatSession } from '../types';
import api from '../lib/api';
import { generateId } from '../lib/utils';

interface ChatState {
  sessions: ChatSession[];
  currentSessionId: string | null;
  isLoading: boolean;
  isStreaming: boolean;
  lastHistoryId: number | null;
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

  // History linking
  setLastHistoryId: (id: number | null) => void;

  // Guest message limit
  incrementGuestCount: () => void;
  resetGuestCount: () => void;

  // Guest → Login sync
  syncGuestMessages: () => Promise<void>;

  // Getters
  getCurrentSession: () => ChatSession | undefined;
  getMessages: () => ChatMessage[];
}

const createNewSession = (title?: string): ChatSession => ({
  id: generateId(),
  title: title || '새 채팅',
  messages: [],
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
      lastHistoryId: null,
      guestMessageCount: 0,

      createSession: (title?: string) => {
        const session = createNewSession(title);
        set((state) => ({
          sessions: [session, ...state.sessions],
          currentSessionId: session.id,
          lastHistoryId: null,
        }));
        return session.id;
      },

      switchSession: (sessionId: string) => {
        set({ currentSessionId: sessionId, lastHistoryId: null });
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

      setLastHistoryId: (id: number | null) => set({ lastHistoryId: id }),

      incrementGuestCount: () =>
        set((state) => ({ guestMessageCount: state.guestMessageCount + 1 })),

      resetGuestCount: () => set({ guestMessageCount: 0 }),

      syncGuestMessages: async () => {
        const state = get();
        const session = state.sessions.find((s) => s.id === state.currentSessionId);
        if (!session || session.messages.length === 0) return;

        const messages = session.messages;
        let lastSyncedHistoryId: number | null = null;

        for (let i = 0; i < messages.length; i++) {
          const msg = messages[i];
          if (msg.type !== 'user') continue;
          if (msg.synced) continue; // 이미 backend에 저장된 메시지 스킵 (중복 방지)

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
          } catch {
            // History sync failure is non-critical
          }
        }

        set({ lastHistoryId: lastSyncedHistoryId });

        if (lastSyncedHistoryId !== null) {
          set((prev) => ({
            sessions: prev.sessions.map((s) =>
              s.id === prev.currentSessionId
                ? { ...s, messages: [], updated_at: new Date().toISOString() }
                : s
            ),
          }));
        }
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
