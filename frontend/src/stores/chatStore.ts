import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { ChatMessage, ChatSession } from '../types';

interface ChatState {
  sessions: ChatSession[];
  currentSessionId: string | null;
  isLoading: boolean;

  // Session management
  createSession: (title?: string) => string;
  switchSession: (sessionId: string) => void;
  deleteSession: (sessionId: string) => void;
  updateSessionTitle: (sessionId: string, title: string) => void;

  // Message management
  addMessage: (message: ChatMessage) => void;
  setLoading: (loading: boolean) => void;
  clearMessages: () => void;

  // Getters
  getCurrentSession: () => ChatSession | undefined;
  getMessages: () => ChatMessage[];
}

const createNewSession = (title?: string): ChatSession => ({
  id: Date.now().toString(),
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

      createSession: (title?: string) => {
        const session = createNewSession(title);
        set((state) => ({
          sessions: [session, ...state.sessions],
          currentSessionId: session.id,
        }));
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

      setLoading: (loading: boolean) => set({ isLoading: loading }),

      clearMessages: () => {
        const state = get();
        if (!state.currentSessionId) return;
        set((prev) => ({
          sessions: prev.sessions.map((s) =>
            s.id === prev.currentSessionId ? { ...s, messages: [], updated_at: new Date().toISOString() } : s
          ),
        }));
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
      }),
      onRehydrate: () => (state) => {
        // Restore Date objects from serialized strings
        if (state) {
          state.sessions = state.sessions.map((session) => ({
            ...session,
            messages: session.messages.map((msg) => ({
              ...msg,
              timestamp: new Date(msg.timestamp),
            })),
          }));
        }
      },
    }
  )
);
