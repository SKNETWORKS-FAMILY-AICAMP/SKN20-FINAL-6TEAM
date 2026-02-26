import React, { useState, useRef, useEffect, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Card,
  CardBody,
  Typography,
  IconButton,
  Chip,
} from '@material-tailwind/react';
import { PaperAirplaneIcon, PlusIcon, StopIcon } from '@heroicons/react/24/solid';
import { PaperClipIcon, XMarkIcon, DocumentArrowDownIcon } from '@heroicons/react/24/outline';
import api from '../lib/api';
import { useChatStore } from '../stores/chatStore';
import { useAuthStore } from '../stores/authStore';
import { useNotificationStore } from '../stores/notificationStore';
import { useChat } from '../hooks/useChat';
import { useDisplayUserType } from '../hooks/useDisplayUserType';
import { useNotifications } from '../hooks/useNotifications';
import { AGENT_NAMES, AGENT_COLORS, type Company, type Schedule } from '../types';
import { USER_QUICK_QUESTIONS } from '../lib/constants';
import { getSeasonalQuestions } from '../lib/seasonalQuestions';
import { ResponseProgress } from '../components/chat/ResponseProgress';
import { SourceReferences } from '../components/chat/SourceReferences';
import { ActionButtons } from '../components/chat/ActionButtons';
import { NotificationToast } from '../components/layout/NotificationToast';
import { PageHeader } from '../components/common/PageHeader';
import { stripSourcesSection, generateId } from '../lib/utils';
import { modifyDocument, fileToBase64, downloadDocumentResponse } from '../lib/documentApi';

const MAX_VISIBLE_TOASTS = 5;

const normalizeNotificationSchedules = (value: unknown): Schedule[] => {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.filter(
    (item): item is Schedule =>
      typeof item === 'object' &&
      item !== null &&
      typeof (item as Schedule).schedule_id === 'number' &&
      typeof (item as Schedule).schedule_name === 'string' &&
      typeof (item as Schedule).start_date === 'string' &&
      typeof (item as Schedule).end_date === 'string'
  );
};

const normalizeNotificationCompanies = (value: unknown): Company[] => {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.filter(
    (item): item is Company =>
      typeof item === 'object' &&
      item !== null &&
      typeof (item as Company).company_id === 'number' &&
      typeof (item as Company).com_name === 'string'
  );
};

const MainPage: React.FC = () => {
  const { isAuthenticated, user } = useAuthStore();
  const { notifications, toastQueue, dismissToast } = useNotificationStore();
  const displayUserType = useDisplayUserType();
  const { sessions, currentSessionId, createSession, isStreaming, addMessage } = useChatStore();
  const { sendMessage, isLoading, stopStreaming } = useChat();
  const [inputValue, setInputValue] = useState('');
  const [notificationSchedules, setNotificationSchedules] = useState<Schedule[]>([]);
  const [notificationCompanyNameById, setNotificationCompanyNameById] = useState<
    Record<number, string>
  >({});
  const [attachedFile, setAttachedFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [isFileProcessing, setIsFileProcessing] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const currentSession = sessions.find((s) => s.id === currentSessionId);
  const messages = currentSession?.messages || [];
  const visibleToastNotifications = toastQueue
    .slice(0, MAX_VISIBLE_TOASTS)
    .map((toastId) => notifications.find((notification) => notification.id === toastId) ?? null)
    .filter((notification): notification is NonNullable<typeof notification> => notification !== null);

  useNotifications(notificationSchedules, notificationCompanyNameById);

  const prevSessionIdRef = useRef<string | null>(null);
  const prevMessagesLengthRef = useRef<number>(0);

  const scrollToBottom = (instant = false) => {
    messagesEndRef.current?.scrollIntoView({ behavior: instant ? 'instant' : 'smooth' });
  };

  // 스크롤 로직: 세션 변경 시 즉시, 메시지 추가 시 부드럽게
  useEffect(() => {
    const sessionChanged = prevSessionIdRef.current !== currentSessionId;
    const messagesAdded = messages.length > prevMessagesLengthRef.current;

    if (sessionChanged) {
      scrollToBottom(true);
    } else if (messagesAdded) {
      scrollToBottom(false);
    }

    prevSessionIdRef.current = currentSessionId;
    prevMessagesLengthRef.current = messages.length;
  }, [currentSessionId, messages.length]);

  // 스트리밍 중 스크롤 따라가기
  useEffect(() => {
    if (isStreaming) {
      const interval = setInterval(() => scrollToBottom(false), 100);
      return () => clearInterval(interval);
    }
  }, [isStreaming]);

  useEffect(() => {
    if (!isAuthenticated) {
      setNotificationSchedules([]);
      setNotificationCompanyNameById({});
      return;
    }

    let isMounted = true;

    const fetchSchedulesForNotifications = async () => {
      try {
        const [schedulesResult, companiesResult] = await Promise.allSettled([
          api.get('/schedules'),
          api.get('/companies'),
        ]);
        if (!isMounted) {
          return;
        }

        if (schedulesResult.status === 'fulfilled') {
          setNotificationSchedules(normalizeNotificationSchedules(schedulesResult.value.data));
        } else {
          setNotificationSchedules([]);
          console.error('Failed to fetch schedules for notifications:', schedulesResult.reason);
        }

        if (companiesResult.status === 'fulfilled') {
          const companies = normalizeNotificationCompanies(companiesResult.value.data);
          const nextCompanyNameById = companies.reduce<Record<number, string>>((acc, company) => {
            acc[company.company_id] = company.com_name;
            return acc;
          }, {});
          setNotificationCompanyNameById(nextCompanyNameById);
        } else {
          setNotificationCompanyNameById({});
          console.error('Failed to fetch companies for notifications:', companiesResult.reason);
        }
      } catch (error) {
        console.error('Failed to fetch schedules for notifications:', error);
      }
    };

    fetchSchedulesForNotifications();

    return () => {
      isMounted = false;
    };
  }, [isAuthenticated]);

  const handleSendMessage = async (message: string) => {
    if (!message.trim() || isLoading || isStreaming || isFileProcessing) return;

    // 파일 첨부 + 수정 지시 → 문서 수정 플로우
    if (attachedFile) {
      setInputValue('');
      const file = attachedFile;
      setAttachedFile(null);
      setFileError(null);
      setIsFileProcessing(true);

      // 사용자 메시지 표시
      const userMsg = {
        id: generateId(),
        type: 'user' as const,
        content: `[${file.name}] ${message}`,
        timestamp: new Date(),
      };
      addMessage(userMsg);

      try {
        const base64 = await fileToBase64(file);
        const ext = file.name.split('.').pop()?.toLowerCase() || 'docx';
        const result = await modifyDocument(base64, file.name, message, ext === 'pdf' ? 'pdf' : 'docx');

        if (result.success) {
          downloadDocumentResponse(result);
          addMessage({
            id: generateId(),
            type: 'assistant',
            content: `문서가 수정되었습니다. **${result.file_name}** 파일이 다운로드됩니다.`,
            agent_code: 'A0000008',
            timestamp: new Date(),
          });
        } else {
          addMessage({
            id: generateId(),
            type: 'assistant',
            content: result.message || '문서 수정에 실패했습니다.',
            agent_code: 'A0000008',
            timestamp: new Date(),
          });
        }
      } catch {
        addMessage({
          id: generateId(),
          type: 'assistant',
          content: '문서 수정 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.',
          agent_code: 'A0000008',
          timestamp: new Date(),
        });
      } finally {
        setIsFileProcessing(false);
        requestAnimationFrame(() => inputRef.current?.focus());
      }
      return;
    }

    setInputValue('');
    await sendMessage(message);
    // 메시지 전송 완료 후 focus 복원
    requestAnimationFrame(() => inputRef.current?.focus());
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleSendMessage(inputValue);
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    // 파일 입력 초기화 (같은 파일 재선택 허용)
    e.target.value = '';

    const ext = file.name.split('.').pop()?.toLowerCase();
    if (!ext || !['docx', 'pdf'].includes(ext)) {
      setFileError('DOCX 또는 PDF 파일만 지원합니다.');
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setFileError('파일 크기는 10MB 이하만 지원합니다.');
      return;
    }
    setFileError(null);
    setAttachedFile(file);
  };

  const handleNewChat = () => {
    createSession();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Escape') {
      inputRef.current?.blur();
    }
  };

  // Dynamic quick questions based on display user type + seasonal questions
  const quickQuestions = useMemo(() => {
    const seasonalQuestions = getSeasonalQuestions();
    const baseQuestions = USER_QUICK_QUESTIONS[displayUserType] || USER_QUICK_QUESTIONS['U0000002'];
    return [...baseQuestions.slice(0, 4), ...seasonalQuestions.slice(0, 2)];
  }, [displayUserType]);

  return (
    <div className="flex h-full min-h-0 flex-col">
      {isAuthenticated &&
        visibleToastNotifications.map((notification, index) => (
          <NotificationToast
            key={notification.id}
            notification={notification}
            onClose={() => dismissToast(notification.id)}
            placement="bell-side"
            stackIndex={index}
          />
        ))}
      {/* Header */}
      <PageHeader
        title={'\u0041\u0049 \uC0C1\uB2F4'}
        description={'\uCC3D\uC5C5, \uC138\uBB34, \uB178\uBB34, \uBC95\uB960, \uC9C0\uC6D0\uC0AC\uC5C5, \uB9C8\uCF00\uD305 \uD1B5\uD569 \uC0C1\uB2F4'}
      />

      {/* Quick questions */}
      <div className="p-4 bg-gray-50 border-b">
        <Typography variant="small" color="gray" className="mb-2 !text-gray-700">
          빠른 질문
        </Typography>
        <div className="flex flex-wrap gap-2">
          {quickQuestions.map((item, index) => (
            <button
              key={index}
              onClick={() => handleSendMessage(item.question)}
              className="px-3 py-1.5 text-sm bg-white border rounded-full hover:bg-blue-50 hover:border-blue-300 transition-colors"
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      {/* Messages area */}
      <div className="min-h-0 flex-1 overflow-auto p-4 space-y-4">
        {!currentSessionId || messages.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center text-gray-500">
              <Typography variant="h6" color="gray" className="mb-2 !text-gray-800">
                {user
                  ? `${user.username}님, 환영합니다!`
                  : 'Bizi에 오신 것을 환영합니다!'}
              </Typography>
              <Typography variant="small" color="gray" className="mb-4 !text-gray-700">
                궁금한 점을 자유롭게 물어보세요.
              </Typography>
              {!currentSessionId && sessions.length > 0 && (
                <button
                  onClick={handleNewChat}
                  className="inline-flex items-center gap-1 px-4 py-2 text-sm bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
                >
                  <PlusIcon className="h-4 w-4" />
                  새 채팅 시작하기
                </button>
              )}
            </div>
          </div>
        ) : (
          messages.map((msg) => {
            // 빈 어시스턴트 메시지 숨김 (스트리밍 시작 전 placeholder)
            if (msg.type === 'assistant' && msg.content === '') return null;
            return (
              <div
                key={msg.id}
                className={`flex ${msg.type === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <Card
                  className={`max-w-[70%] ${
                    msg.type === 'user' ? 'bg-blue-500 text-white' : 'bg-white'
                  }`}
                >
                  <CardBody className="p-3">
                    {msg.type === 'assistant' && msg.agent_code && (
                      <div className="mb-2 flex flex-wrap gap-1">
                        {msg.agent_codes && msg.agent_codes.length > 1 ? (
                          msg.agent_codes.map((code) => (
                            <Chip
                              key={code}
                              size="sm"
                              value={AGENT_NAMES[code]}
                              className={`${AGENT_COLORS[code]} text-white`}
                            />
                          ))
                        ) : (
                          <Chip
                            size="sm"
                            value={AGENT_NAMES[msg.agent_code]}
                            className={`${AGENT_COLORS[msg.agent_code]} text-white`}
                          />
                        )}
                      </div>
                    )}
                    {msg.type === 'assistant' ? (
                      <>
                        <div className="markdown-body text-sm text-gray-800">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {stripSourcesSection(msg.content)}
                          </ReactMarkdown>
                        </div>
                        {msg.sources && msg.sources.length > 0 && (
                          <SourceReferences sources={msg.sources} />
                        )}
                        {msg.actions && msg.actions.length > 0 && (
                          <ActionButtons actions={msg.actions} />
                        )}
                      </>
                    ) : (
                      <Typography variant="small" className="text-white">
                        {(() => {
                          const lines = msg.content.split('\n');
                          return lines.map((line, i) => (
                            <React.Fragment key={i}>
                              {line}
                              {i < lines.length - 1 && <br />}
                            </React.Fragment>
                          ));
                        })()}
                      </Typography>
                    )}
                    <Typography
                      variant="small"
                      className={`text-xs mt-1 ${
                        msg.type === 'user' ? 'text-blue-100' : 'text-gray-400'
                      }`}
                    >
                      {new Date(msg.timestamp).toLocaleTimeString('ko-KR', {
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </Typography>
                  </CardBody>
                </Card>
              </div>
            );
          })
        )}
        <ResponseProgress isLoading={isLoading} isStreaming={isStreaming} isFileProcessing={isFileProcessing} />
        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="bg-transparent px-4 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-3 sm:px-6 sm:pt-4">
        <div className="max-w-4xl mx-auto">
          {/* 파일 첨부 미리보기 */}
          {attachedFile && (
            <div className="flex items-center gap-2 px-3 py-2 mb-1 bg-blue-50 border border-blue-200 rounded-t-2xl text-sm text-blue-700">
              <DocumentArrowDownIcon className="h-4 w-4 flex-shrink-0" />
              <span className="truncate">{attachedFile.name}</span>
              <button
                type="button"
                onClick={() => setAttachedFile(null)}
                className="ml-auto p-0.5 hover:bg-blue-100 rounded"
              >
                <XMarkIcon className="h-4 w-4" />
              </button>
            </div>
          )}
          {fileError && (
            <p className="px-3 py-1 mb-1 text-xs text-red-500">{fileError}</p>
          )}
          <form
            onSubmit={handleSubmit}
            className={`flex items-center gap-2 p-3 bg-white shadow-lg border border-gray-200 ${
              attachedFile ? 'rounded-b-2xl' : 'rounded-2xl'
            }`}
          >
            {/* 파일 첨부 버튼 */}
            <input
              ref={fileInputRef}
              type="file"
              accept=".docx,.pdf"
              onChange={handleFileSelect}
              className="hidden"
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={isLoading || isStreaming || isFileProcessing}
              className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              title="파일 첨부 (DOCX, PDF)"
            >
              <PaperClipIcon className="h-5 w-5" />
            </button>
            <div className="flex-1">
              <input
                ref={inputRef}
                type="text"
                placeholder={attachedFile ? '수정할 내용을 입력하세요...' : '메시지를 입력하세요...'}
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                className="w-full px-3 py-2 text-sm border-0 focus:outline-none focus:ring-0 bg-transparent placeholder-gray-400"
              />
            </div>
            {isLoading || isStreaming || isFileProcessing ? (
              <IconButton
                type="button"
                color="blue"
                onClick={stopStreaming}
                className="rounded-xl !bg-gray-400 hover:!bg-gray-500"
              >
                <StopIcon className="h-5 w-5" />
              </IconButton>
            ) : (
              <IconButton
                type="submit"
                color="blue"
                disabled={!inputValue.trim()}
                className="rounded-xl"
              >
                <PaperAirplaneIcon className="h-5 w-5" />
              </IconButton>
            )}
          </form>
          <Typography variant="small" color="gray" className="text-center mt-3 mb-2 text-xs !text-gray-600">
            Bizi는 AI 기반 상담 서비스로, 법적 조언이 아닙니다. 중요한 결정은 전문가와 상담하세요.
          </Typography>
        </div>
      </div>
    </div>
  );
};

export default MainPage;
