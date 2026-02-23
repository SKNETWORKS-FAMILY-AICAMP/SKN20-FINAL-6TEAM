import { useCallback, useRef, useEffect } from 'react';
import { useChatStore } from '../stores/chatStore';
import { useAuthStore } from '../stores/authStore';
import ragApi, { isRagEnabled, isStreamingEnabled, checkRagHealth, streamChat } from '../lib/rag';
import api from '../lib/api';
import type { ChatMessage, AgentCode, RagChatResponse, EvaluationData, SourceReference, RagActionSuggestion } from '../types';
import { GUEST_MESSAGE_LIMIT, domainToAgentCode } from '../lib/constants';
import { generateId } from '../lib/utils';
import { getMockResponse } from '../lib/mockResponses';

const ERROR_MESSAGE = '죄송합니다. 응답을 생성하는 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.';
const GUEST_LIMIT_MESSAGE = '무료 체험 메시지를 모두 사용했습니다. 로그인하시면 무제한으로 상담을 이용할 수 있습니다.';

export const useChat = () => {
  const { addMessage, updateMessage, setLoading, setStreaming, isLoading, setLastHistoryId, updateMessageInSession, setLastHistoryIdForSession, guestMessageCount, incrementGuestCount } = useChatStore();
  const { isAuthenticated } = useAuthStore();
  const streamingContentRef = useRef<string>('');
  const abortControllerRef = useRef<AbortController | null>(null);
  const rafRef = useRef<number | null>(null);

  // Cleanup on unmount: abort any in-flight stream
  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
      }
    };
  }, []);

  const sendMessage = useCallback(
    async (message: string) => {
      if (!message.trim() || isLoading) return;

      // Guest message limit check
      if (!isAuthenticated && guestMessageCount >= GUEST_MESSAGE_LIMIT) {
        const limitMessage: ChatMessage = {
          id: generateId(),
          type: 'assistant',
          content: GUEST_LIMIT_MESSAGE,
          agent_code: 'A0000001',
          timestamp: new Date(),
        };
        addMessage(limitMessage);
        return;
      }

      // Abort any previous in-flight stream
      abortControllerRef.current?.abort();

      // Build history BEFORE adding current message to avoid self-duplication in RAG augmentation
      const MAX_HISTORY_MESSAGES = 6; // 3턴 (RAG QuestionDecomposer MAX_HISTORY_TURNS=3)
      const previousMessages = useChatStore.getState().getMessages();
      const history = previousMessages
        .filter(m =>
          (m.type === 'user' || m.type === 'assistant') &&
          !m.content.startsWith('죄송합니다. 응답을 생성하는 중') &&
          !m.content.startsWith('무료 체험 메시지를 모두')
        )
        .slice(-MAX_HISTORY_MESSAGES)
        .map(m => ({
          role: m.type === 'user' ? 'user' : 'assistant' as const,
          content: m.content,
        }));

      // Add user message
      const userMessage: ChatMessage = {
        id: generateId(),
        type: 'user',
        content: message,
        timestamp: new Date(),
      };
      addMessage(userMessage);
      setLoading(true);

      // 세션 ID 고정 — 비동기 중 세션 전환 시에도 올바른 세션에 업데이트
      const targetSessionId = useChatStore.getState().currentSessionId!;

      try {
        let response: string;
        let agentCode: AgentCode;
        let evaluationData: EvaluationData | null = null;
        let savedAssistantMsgId: string | null = null;

        // Check if RAG service is available
        const ragAvailable = isRagEnabled() && await checkRagHealth();

        if (ragAvailable) {
          const useStreaming = isStreamingEnabled();

          if (useStreaming) {
            // Streaming mode (SSE)
            const assistantMessageId = generateId();
            streamingContentRef.current = '';
            const collectedSources: SourceReference[] = [];
            const collectedActions: RagActionSuggestion[] = [];

            // Create new AbortController for this stream
            const abortController = new AbortController();
            abortControllerRef.current = abortController;

            // Add empty assistant message first (without agent_code - will be set on done)
            const initialMessage: ChatMessage = {
              id: assistantMessageId,
              type: 'assistant',
              content: '',
              timestamp: new Date(),
            };
            addMessage(initialMessage);

            let finalDomain = 'general';

            await streamChat(message, {
              onToken: (token) => {
                if (streamingContentRef.current === '') {
                  setStreaming(true);
                }
                streamingContentRef.current += token;
                // RAF-based throttle: batch store updates to ~60fps max
                if (rafRef.current === null) {
                  rafRef.current = requestAnimationFrame(() => {
                    updateMessage(assistantMessageId, {
                      content: streamingContentRef.current,
                    });
                    rafRef.current = null;
                  });
                }
              },
              onSource: (source) => {
                collectedSources.push(source);
              },
              onAction: (action) => {
                collectedActions.push(action);
              },
              onDone: (metadata) => {
                // Cancel pending RAF and flush final content
                if (rafRef.current !== null) {
                  cancelAnimationFrame(rafRef.current);
                  rafRef.current = null;
                }
                setStreaming(false);
                finalDomain = metadata?.domain || 'general';
                evaluationData = (metadata?.evaluation_data as EvaluationData) || null;
                const finalAgentCode = domainToAgentCode(finalDomain);

                // Build multi-domain agent_codes from metadata.domains
                const domains = metadata?.domains;
                let agentCodes: AgentCode[] | undefined;
                if (domains && domains.length > 1) {
                  const codes = [...new Set(domains.map(domainToAgentCode))];
                  if (codes.length > 1) {
                    agentCodes = codes;
                  }
                }

                updateMessage(assistantMessageId, {
                  content: streamingContentRef.current,
                  agent_code: finalAgentCode,
                  ...(agentCodes ? { agent_codes: agentCodes } : {}),
                  ...(collectedSources.length > 0 ? { sources: collectedSources } : {}),
                  ...(collectedActions.length > 0 ? { actions: collectedActions } : {}),
                });
              },
              onError: (error) => {
                if (rafRef.current !== null) {
                  cancelAnimationFrame(rafRef.current);
                  rafRef.current = null;
                }
                setStreaming(false);
                updateMessage(assistantMessageId, {
                  content: ERROR_MESSAGE,
                });
                console.error('Streaming error:', error);
              },
            }, abortController.signal, history);

            response = streamingContentRef.current;
            agentCode = domainToAgentCode(finalDomain);
            savedAssistantMsgId = assistantMessageId;
          } else {
            // Non-streaming mode
            const ragResponse = await ragApi.post<RagChatResponse>('/rag/chat', {
              message,
              ...(history.length ? { history } : {}),
            });
            response = ragResponse.data.content;
            agentCode = domainToAgentCode(ragResponse.data.domain);
            evaluationData = ragResponse.data.evaluation_data ?? null;

            // Build multi-domain agent_codes
            const ragDomains = ragResponse.data.domains;
            let nonStreamAgentCodes: AgentCode[] | undefined;
            if (ragDomains && ragDomains.length > 1) {
              const codes = [...new Set(ragDomains.map(domainToAgentCode))];
              if (codes.length > 1) {
                nonStreamAgentCodes = codes;
              }
            }

            const ragSources: SourceReference[] = (ragResponse.data.sources || []).map((s) => ({
              title: s.title || '',
              source: s.source || '',
              url: (s.metadata?.source_url as string) || '',
            }));

            const ragActions: RagActionSuggestion[] = ragResponse.data.actions || [];

            const assistantMessage: ChatMessage = {
              id: generateId(),
              type: 'assistant',
              content: response,
              agent_code: agentCode,
              ...(nonStreamAgentCodes ? { agent_codes: nonStreamAgentCodes } : {}),
              ...(ragSources.length > 0 ? { sources: ragSources } : {}),
              ...(ragActions.length > 0 ? { actions: ragActions } : {}),
              timestamp: new Date(),
            };
            addMessage(assistantMessage);
            savedAssistantMsgId = assistantMessage.id;
          }
        } else {
          // Mock response (fallback when RAG is disabled or unavailable)
          const mockResult = await getMockResponse(message);
          response = mockResult.response;
          agentCode = mockResult.agent_code;

          const assistantMessage: ChatMessage = {
            id: generateId(),
            type: 'assistant',
            content: response,
            agent_code: agentCode,
            timestamp: new Date(),
          };
          addMessage(assistantMessage);
          savedAssistantMsgId = assistantMessage.id;
        }

        // Save to backend history if authenticated
        if (isAuthenticated) {
          try {
            // 고정된 세션의 lastHistoryId를 parent로 사용
            const targetSession = useChatStore.getState().sessions.find(s => s.id === targetSessionId);
            const parentHistoryId = targetSession?.lastHistoryId ?? null;

            const historyResponse = await api.post('/histories', {
              agent_code: agentCode,
              question: message,
              answer: response,
              parent_history_id: parentHistoryId,
              evaluation_data: evaluationData,
            });
            // 고정된 세션에 lastHistoryId 설정 (세션 전환 중에도 안전)
            setLastHistoryIdForSession(targetSessionId, historyResponse.data.history_id);
            // 고정된 세션의 메시지에 synced 마킹 (중복 저장 방지)
            updateMessageInSession(targetSessionId, userMessage.id, { synced: true });
            if (savedAssistantMsgId) {
              updateMessageInSession(targetSessionId, savedAssistantMsgId, { synced: true });
            }
          } catch {
            // History save failure is non-critical
          }
        } else {
          incrementGuestCount();
        }
      } catch (err) {
        // Ignore AbortError (user-initiated cancellation)
        if (err instanceof DOMException && err.name === 'AbortError') return;

        const errorMessage: ChatMessage = {
          id: generateId(),
          type: 'assistant',
          content: ERROR_MESSAGE,
          agent_code: 'A0000001',
          timestamp: new Date(),
        };
        addMessage(errorMessage);
      } finally {
        // Cancel any pending RAF
        if (rafRef.current !== null) {
          cancelAnimationFrame(rafRef.current);
          rafRef.current = null;
        }
        setStreaming(false);
        setLoading(false);
        abortControllerRef.current = null;
      }
    },
    [addMessage, updateMessage, setLoading, setStreaming, isLoading, isAuthenticated, setLastHistoryId, updateMessageInSession, setLastHistoryIdForSession, guestMessageCount, incrementGuestCount]
  );

  return { sendMessage, isLoading };
};
