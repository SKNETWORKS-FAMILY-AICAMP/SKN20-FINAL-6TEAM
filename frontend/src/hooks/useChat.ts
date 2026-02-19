import { useCallback, useRef, useEffect } from 'react';
import { useChatStore } from '../stores/chatStore';
import { useAuthStore } from '../stores/authStore';
import ragApi, { isRagEnabled, isStreamingEnabled, checkRagHealth, streamChat } from '../lib/rag';
import api from '../lib/api';
import type { ChatMessage, AgentCode, RagChatResponse, EvaluationData } from '../types';
import { GUEST_MESSAGE_LIMIT, domainToAgentCode } from '../lib/constants';
import { generateId } from '../lib/utils';
import { getMockResponse } from '../lib/mockResponses';

const ERROR_MESSAGE = '죄송합니다. 응답을 생성하는 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.';
const GUEST_LIMIT_MESSAGE = '무료 체험 메시지를 모두 사용했습니다. 로그인하시면 무제한으로 상담을 이용할 수 있습니다.';

export const useChat = () => {
  const { addMessage, updateMessage, setLoading, setStreaming, isLoading, lastHistoryId, setLastHistoryId, guestMessageCount, incrementGuestCount } = useChatStore();
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

      // Add user message
      const userMessage: ChatMessage = {
        id: generateId(),
        type: 'user',
        content: message,
        timestamp: new Date(),
      };
      addMessage(userMessage);
      setLoading(true);

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
            }, abortController.signal);

            response = streamingContentRef.current;
            agentCode = domainToAgentCode(finalDomain);
            savedAssistantMsgId = assistantMessageId;
          } else {
            // Non-streaming mode
            const ragResponse = await ragApi.post<RagChatResponse>('/rag/chat', {
              message,
            });
            response = ragResponse.data.content;
            agentCode = domainToAgentCode(ragResponse.data.domain);
            evaluationData = ((ragResponse.data as unknown as Record<string, unknown>).evaluation_data as EvaluationData | undefined) ?? null;

            // Build multi-domain agent_codes
            const ragDomains = ragResponse.data.domains;
            let nonStreamAgentCodes: AgentCode[] | undefined;
            if (ragDomains && ragDomains.length > 1) {
              const codes = [...new Set(ragDomains.map(domainToAgentCode))];
              if (codes.length > 1) {
                nonStreamAgentCodes = codes;
              }
            }

            const assistantMessage: ChatMessage = {
              id: generateId(),
              type: 'assistant',
              content: response,
              agent_code: agentCode,
              ...(nonStreamAgentCodes ? { agent_codes: nonStreamAgentCodes } : {}),
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
            const historyResponse = await api.post('/histories', {
              agent_code: agentCode,
              question: message,
              answer: response,
              parent_history_id: lastHistoryId,
              evaluation_data: evaluationData,
            });
            setLastHistoryId(historyResponse.data.history_id);
            // Mark messages as synced to prevent duplicate save on re-login
            updateMessage(userMessage.id, { synced: true });
            if (savedAssistantMsgId) {
              updateMessage(savedAssistantMsgId, { synced: true });
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
    [addMessage, updateMessage, setLoading, setStreaming, isLoading, isAuthenticated, lastHistoryId, setLastHistoryId, guestMessageCount, incrementGuestCount]
  );

  return { sendMessage, isLoading };
};
