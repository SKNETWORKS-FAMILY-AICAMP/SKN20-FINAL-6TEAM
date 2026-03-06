import { useCallback, useEffect, useRef } from 'react';
import { useChatStore } from '../stores/chatStore';
import { useAuthStore } from '../stores/authStore';
import { useNotificationStore } from '../stores/notificationStore';
import ragApi, { isRagEnabled, isStreamingEnabled, checkRagHealth, streamChat } from '../lib/rag';
import type { ChatMessage, AgentCode, RagChatResponse, EvaluationData, SourceReference, RagActionSuggestion } from '../types';
import { GUEST_MESSAGE_LIMIT, AUTHENTICATED_DAILY_LIMIT, AUTHENTICATED_LIMIT_MESSAGE, domainToAgentCode } from '../lib/constants';
import { generateId } from '../lib/utils';
import { getMockResponse } from '../lib/mockResponses';

const ERROR_MESSAGE = '\uC8C4\uC1A1\uD569\uB2C8\uB2E4. \uC751\uB2F5\uC744 \uC0DD\uC131\uD558\uB294 \uC911 \uC624\uB958\uAC00 \uBC1C\uC0DD\uD588\uC2B5\uB2C8\uB2E4. \uC7A0\uC2DC \uD6C4 \uB2E4\uC2DC \uC2DC\uB3C4\uD574\uC8FC\uC138\uC694.';
const GUEST_LIMIT_MESSAGE = '\uBB34\uB8CC \uCCB4\uD5D8 \uBA54\uC2DC\uC9C0\uB97C \uBAA8\uB450 \uC0AC\uC6A9\uD588\uC2B5\uB2C8\uB2E4. \uB85C\uADF8\uC778\uD558\uC2DC\uBA74 \uBB34\uC81C\uD55C\uC73C\uB85C \uC0C1\uB2F4\uC744 \uC774\uC6A9\uD560 \uC218 \uC788\uC2B5\uB2C8\uB2E4.';
const ANSWER_COMPLETE_NOTIFICATION_TITLE = '\uB2F5\uBCC0 \uC644\uB8CC';
const ANSWER_COMPLETE_NOTIFICATION_MESSAGE = '\uC694\uCCAD\uD558\uC2E0 \uB2F5\uBCC0 \uC0DD\uC131\uC774 \uC644\uB8CC\uB418\uC5C8\uC2B5\uB2C8\uB2E4.';
const ANSWER_COMPLETE_NOTIFICATION_LINK = '/';

const shouldShowAnswerCompleteNotification = (): boolean => {
  if (typeof document === 'undefined' || document.visibilityState !== 'hidden') {
    return false;
  }

  const { isAuthenticated, notificationSettings, notificationSettingsLoaded } = useAuthStore.getState();
  return isAuthenticated && notificationSettingsLoaded && notificationSettings.answer_complete;
};

const addAnswerCompleteNotification = (): void => {
  const addNotification = useNotificationStore.getState().addNotification;
  addNotification({
    id: `answer-complete-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    title: ANSWER_COMPLETE_NOTIFICATION_TITLE,
    message: ANSWER_COMPLETE_NOTIFICATION_MESSAGE,
    type: 'info',
    link: ANSWER_COMPLETE_NOTIFICATION_LINK,
  });
};

const isAbortError = (err: unknown): boolean => {
  if (err instanceof DOMException && err.name === 'AbortError') return true;
  // Some browsers throw TypeError on aborted ReadableStream reads
  if (err instanceof TypeError && /aborted|abort|cancel/i.test(err.message)) return true;
  return false;
};

const sessionAbortControllers = new Map<string, AbortController>();

export const useChat = () => {
  const {
    addMessageToSession,
    isSyncing,
    updateMessageInSession,
    guestMessageCount,
    incrementGuestCount,
    authenticatedMessageCount,
    incrementAuthenticatedCount,
    startSessionResponse,
    markSessionStreaming,
    finishSessionResponse,
    isSessionResponding,
    canStartNewResponse,
  } = useChatStore();
  const { isAuthenticated } = useAuthStore();
  const streamingContentRefBySession = useRef<Map<string, string>>(new Map());
  const rafRefBySession = useRef<Map<string, number>>(new Map());
  const activeStreamingMessagesRef = useRef<Map<string, string>>(new Map());

  const cancelPendingRaf = useCallback((sessionId: string) => {
    const pendingRafId = rafRefBySession.current.get(sessionId);
    if (pendingRafId !== undefined) {
      cancelAnimationFrame(pendingRafId);
      rafRefBySession.current.delete(sessionId);
    }
  }, []);

  // Cleanup on unmount: flush pending content, let streams continue in background
  useEffect(() => {
    return () => {
      // 1. Cancel pending RAFs (RAF callbacks may not fire after unmount)
      rafRefBySession.current.forEach((rafId) => cancelAnimationFrame(rafId));
      rafRefBySession.current.clear();

      // 2. Flush pending streaming content to Zustand (so remount shows latest)
      activeStreamingMessagesRef.current.forEach((messageId, sessionId) => {
        const pendingContent = streamingContentRefBySession.current.get(sessionId);
        if (pendingContent) {
          useChatStore.getState().updateMessageInSession(sessionId, messageId, {
            content: pendingContent,
          });
        }
      });
      activeStreamingMessagesRef.current.clear();
      // NOTE: streamingContentRefBySession는 clear하지 않음 — 진행 중인 async 코드가 필요
      // NOTE: 스트림 abort 안 함 — 백그라운드에서 계속 실행
      // NOTE: finishSessionResponse 안 함 — finally 블록이 처리
    };
  }, []);

  const sendMessage = useCallback(
    async (message: string) => {
      if (!message.trim() || isSyncing) return;

      const targetSessionId = useChatStore.getState().ensureCurrentSession();
      if (isSessionResponding(targetSessionId)) return;
      if (!canStartNewResponse(targetSessionId)) return;

      // Guest message limit check
      if (!isAuthenticated && guestMessageCount >= GUEST_MESSAGE_LIMIT) {
        const limitMessage: ChatMessage = {
          id: generateId(),
          type: 'assistant',
          content: GUEST_LIMIT_MESSAGE,
          agent_code: 'A0000001',
          timestamp: new Date(),
        };
        addMessageToSession(targetSessionId, limitMessage);
        return;
      }

      // Authenticated user daily quota check
      if (isAuthenticated && AUTHENTICATED_DAILY_LIMIT !== null
          && authenticatedMessageCount >= AUTHENTICATED_DAILY_LIMIT) {
        const limitMessage: ChatMessage = {
          id: generateId(),
          type: 'assistant',
          content: AUTHENTICATED_LIMIT_MESSAGE,
          agent_code: 'A0000001',
          timestamp: new Date(),
        };
        addMessageToSession(targetSessionId, limitMessage);
        return;
      }

      // Build history BEFORE adding current message to avoid self-duplication in RAG augmentation
      const MAX_HISTORY_MESSAGES = 6; // 3 turns (RAG QuestionDecomposer MAX_HISTORY_TURNS=3)
      const previousMessages = useChatStore.getState().sessions.find((s) => s.id === targetSessionId)?.messages || [];
      const history = previousMessages
        .filter((m) =>
          (m.type === 'user' || m.type === 'assistant')
          && m.content.trim() !== ''
          && !m.content.startsWith('\uC8C4\uC1A1\uD569\uB2C8\uB2E4. \uC751\uB2F5\uC744 \uC0DD\uC131\uD558\uB294 \uC911')
          && !m.content.startsWith('\uBB34\uB8CC \uCCB4\uD5D8 \uBA54\uC2DC\uC9C0\uB97C \uBAA8\uB450')
        )
        .slice(-MAX_HISTORY_MESSAGES)
        .map((m) => ({
          role: m.type === 'user' ? 'user' : 'assistant' as const,
          content: m.content,
        }));

      // Add user message
      const userMessage: ChatMessage = {
        id: generateId(),
        type: 'user',
        content: message,
        timestamp: new Date(),
        synced: isAuthenticated,
      };
      addMessageToSession(targetSessionId, userMessage);
      startSessionResponse(targetSessionId);

      let streamAborted = false;
      try {
        let response: string;
        let agentCode: AgentCode;
        let evaluationData: EvaluationData | null = null;

        // Check if RAG service is available
        const ragAvailable = isRagEnabled() && await checkRagHealth();

        if (ragAvailable) {
          const useStreaming = isStreamingEnabled();

          if (useStreaming) {
            // Streaming mode (SSE)
            const assistantMessageId = generateId();
            streamingContentRefBySession.current.set(targetSessionId, '');
            const collectedSources: SourceReference[] = [];
            const collectedActions: RagActionSuggestion[] = [];

            // Create new AbortController for this stream
            const abortController = new AbortController();
            abortController.signal.addEventListener('abort', () => { streamAborted = true; });
            sessionAbortControllers.set(targetSessionId, abortController);

            // Add empty assistant message first (without agent_code - will be set on done)
            const initialMessage: ChatMessage = {
              id: assistantMessageId,
              type: 'assistant',
              content: '',
              timestamp: new Date(),
              synced: isAuthenticated,
            };
            addMessageToSession(targetSessionId, initialMessage);
            activeStreamingMessagesRef.current.set(targetSessionId, assistantMessageId);

            let finalDomain = 'general';

            const session = useChatStore.getState().sessions.find((s) => s.id === targetSessionId);
            const rootHistoryId = session?.rootHistoryId ?? null;

            await streamChat(message, {
              onToken: (token) => {
                const previousContent = streamingContentRefBySession.current.get(targetSessionId) || '';
                if (previousContent === '') {
                  markSessionStreaming(targetSessionId);
                }

                const nextContent = `${previousContent}${token}`;
                streamingContentRefBySession.current.set(targetSessionId, nextContent);

                // RAF-based throttle: batch store updates to ~60fps max
                if (!rafRefBySession.current.has(targetSessionId)) {
                  const rafId = requestAnimationFrame(() => {
                    updateMessageInSession(targetSessionId, assistantMessageId, {
                      content: streamingContentRefBySession.current.get(targetSessionId) || '',
                    });
                    rafRefBySession.current.delete(targetSessionId);
                  });
                  rafRefBySession.current.set(targetSessionId, rafId);
                }
              },
              onSource: (source) => {
                collectedSources.push(source);
              },
              onAction: (action) => {
                collectedActions.push(action);
              },
              onDone: (metadata) => {
                cancelPendingRaf(targetSessionId);
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

                updateMessageInSession(targetSessionId, assistantMessageId, {
                  content: streamingContentRefBySession.current.get(targetSessionId) || '',
                  agent_code: finalAgentCode,
                  ...(agentCodes ? { agent_codes: agentCodes } : {}),
                  ...(collectedSources.length > 0 ? { sources: collectedSources } : {}),
                  ...(collectedActions.length > 0 ? { actions: collectedActions } : {}),
                  ...(evaluationData ? { evaluation_data: evaluationData } : {}),
                  synced: isAuthenticated,
                });
              },
              onError: (error) => {
                if (abortController.signal.aborted) return;
                cancelPendingRaf(targetSessionId);
                updateMessageInSession(targetSessionId, assistantMessageId, {
                  content: ERROR_MESSAGE,
                  ...(collectedActions.length > 0 ? { actions: collectedActions } : {}),
                });
                console.error('Streaming error:', error);
              },
            }, abortController.signal, history, targetSessionId, rootHistoryId);

            response = streamingContentRefBySession.current.get(targetSessionId) || '';
            agentCode = domainToAgentCode(finalDomain);
          } else {
            // Non-streaming mode
            const nonStreamSession = useChatStore.getState().sessions.find((s) => s.id === targetSessionId);
            const nonStreamRootHistoryId = nonStreamSession?.rootHistoryId ?? null;
            const ragResponse = await ragApi.post<RagChatResponse>('/rag/chat', {
              message,
              ...(history.length ? { history } : {}),
              session_id: targetSessionId,
              ...(nonStreamRootHistoryId ? { root_history_id: nonStreamRootHistoryId } : {}),
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
              docDownloadUrl: (s.metadata?.doc_download_url as string) || '',
              formDownloadUrl: (s.metadata?.form_download_url as string) || '',
              formS3Key: (s.metadata?.form_s3_key as string) || '',
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
              synced: isAuthenticated,
            };
            addMessageToSession(targetSessionId, assistantMessage);
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
          addMessageToSession(targetSessionId, assistantMessage);
        }

        if (shouldShowAnswerCompleteNotification()) {
          addAnswerCompleteNotification();
        }
        // Redis-first: authenticated users are auto-saved in RAG session memory (Redis).
        // DB migration is handled by the RAG batch migration process.
        if (!isAuthenticated) {
          incrementGuestCount();
        } else {
          incrementAuthenticatedCount();
        }
      } catch (err) {
        if (isAbortError(err) || streamAborted) return;

        const errorMessage: ChatMessage = {
          id: generateId(),
          type: 'assistant',
          content: ERROR_MESSAGE,
          agent_code: 'A0000001',
          timestamp: new Date(),
        };
        addMessageToSession(targetSessionId, errorMessage);
      } finally {
        cancelPendingRaf(targetSessionId);
        sessionAbortControllers.delete(targetSessionId);
        activeStreamingMessagesRef.current.delete(targetSessionId);
        streamingContentRefBySession.current.delete(targetSessionId);
        finishSessionResponse(targetSessionId);
      }
    },
    [
      addMessageToSession,
      isSyncing,
      guestMessageCount,
      isAuthenticated,
      authenticatedMessageCount,
      updateMessageInSession,
      incrementGuestCount,
      incrementAuthenticatedCount,
      startSessionResponse,
      markSessionStreaming,
      finishSessionResponse,
      isSessionResponding,
      canStartNewResponse,
      cancelPendingRaf,
    ]
  );

  const stopStreaming = useCallback((sessionId?: string) => {
    const targetSessionId = sessionId ?? useChatStore.getState().currentSessionId;
    if (!targetSessionId) return;

    const controller = sessionAbortControllers.get(targetSessionId);
    if (!controller) return;
    controller.abort();
    sessionAbortControllers.delete(targetSessionId);
  }, []);

  return { sendMessage, stopStreaming };
};

