import React, { useState, useRef, useEffect } from 'react';
import {
  Card,
  CardBody,
  Typography,
  Input,
  IconButton,
  Chip,
  Spinner,
} from '@material-tailwind/react';
import { PaperAirplaneIcon } from '@heroicons/react/24/solid';
import { useChatStore } from '../stores/chatStore';
import { useAuthStore } from '../stores/authStore';
import { AGENT_NAMES, AGENT_COLORS, USER_TYPE_NAMES } from '../types';
import type { ChatMessage, AgentCode } from '../types';

// 빠른 질문 버튼
const quickQuestions = [
  { label: '사업자 등록 방법', question: '사업자 등록은 어떻게 하나요?' },
  { label: '법인 설립 절차', question: '법인 설립 절차를 알려주세요.' },
  { label: '부가세 신고', question: '부가가치세 신고는 언제 해야 하나요?' },
  { label: '직원 채용', question: '직원을 채용할 때 필요한 절차가 뭔가요?' },
  { label: '지원사업 찾기', question: '우리 회사에 맞는 정부 지원사업을 추천해주세요.' },
  { label: '근로계약서 작성', question: '근로계약서는 어떻게 작성하나요?' },
];

const MainPage: React.FC = () => {
  const { user } = useAuthStore();
  const { messages, isLoading, addMessage, setLoading } = useChatStore();
  const [inputValue, setInputValue] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSendMessage = async (message: string) => {
    if (!message.trim() || isLoading) return;

    // 사용자 메시지 추가
    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      type: 'user',
      content: message,
      timestamp: new Date(),
    };
    addMessage(userMessage);
    setInputValue('');
    setLoading(true);

    // RAG 미구현 - "구현 중..." 응답
    setTimeout(() => {
      const assistantMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        type: 'assistant',
        content: '구현 중...\n\nRAG 시스템이 아직 연동되지 않았습니다. 멀티에이전트 시스템 구축 후 실제 답변이 제공됩니다.',
        agent_code: 'A001' as AgentCode,
        timestamp: new Date(),
      };
      addMessage(assistantMessage);
      setLoading(false);
    }, 1000);
  };

  const handleQuickQuestion = (question: string) => {
    handleSendMessage(question);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleSendMessage(inputValue);
  };

  return (
    <div className="flex flex-col h-full">
      {/* 헤더 */}
      <div className="p-4 border-b bg-white">
        <div className="flex items-center justify-between">
          <div>
            <Typography variant="h5" color="blue-gray">
              AI 상담
            </Typography>
            <Typography variant="small" color="gray">
              창업, 세무, 노무, 법률, 지원사업, 마케팅 통합 상담
            </Typography>
          </div>
          {user && (
            <Chip
              value={USER_TYPE_NAMES[user.type_code] || user.type_code}
              color="blue"
              variant="ghost"
            />
          )}
        </div>
      </div>

      {/* 빠른 질문 버튼 */}
      <div className="p-4 bg-gray-50 border-b">
        <Typography variant="small" color="gray" className="mb-2">
          빠른 질문
        </Typography>
        <div className="flex flex-wrap gap-2">
          {quickQuestions.map((item, index) => (
            <button
              key={index}
              onClick={() => handleQuickQuestion(item.question)}
              className="px-3 py-1.5 text-sm bg-white border rounded-full hover:bg-blue-50 hover:border-blue-300 transition-colors"
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      {/* 메시지 영역 */}
      <div className="flex-1 overflow-auto p-4 space-y-4">
        {messages.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center text-gray-500">
              <Typography variant="h6" color="gray" className="mb-2">
                BizMate에 오신 것을 환영합니다!
              </Typography>
              <Typography variant="small" color="gray">
                궁금한 점을 자유롭게 물어보세요.
              </Typography>
            </div>
          </div>
        ) : (
          messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex ${msg.type === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <Card
                className={`max-w-[70%] ${
                  msg.type === 'user'
                    ? 'bg-blue-500 text-white'
                    : 'bg-white'
                }`}
              >
                <CardBody className="p-3">
                  {msg.type === 'assistant' && msg.agent_code && (
                    <div className="mb-2">
                      <Chip
                        size="sm"
                        value={AGENT_NAMES[msg.agent_code]}
                        className={`${AGENT_COLORS[msg.agent_code]} text-white`}
                      />
                    </div>
                  )}
                  <Typography
                    variant="small"
                    className={msg.type === 'user' ? 'text-white' : 'text-gray-800'}
                  >
                    {msg.content.split('\n').map((line, i) => (
                      <React.Fragment key={i}>
                        {line}
                        {i < msg.content.split('\n').length - 1 && <br />}
                      </React.Fragment>
                    ))}
                  </Typography>
                  <Typography
                    variant="small"
                    className={`text-xs mt-1 ${
                      msg.type === 'user' ? 'text-blue-100' : 'text-gray-400'
                    }`}
                  >
                    {msg.timestamp.toLocaleTimeString('ko-KR', {
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </Typography>
                </CardBody>
              </Card>
            </div>
          ))
        )}
        {isLoading && (
          <div className="flex justify-start">
            <Card className="bg-white">
              <CardBody className="p-3 flex items-center gap-2">
                <Spinner className="h-4 w-4" />
                <Typography variant="small" color="gray">
                  답변을 생성하고 있습니다...
                </Typography>
              </CardBody>
            </Card>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* 입력 영역 */}
      <div className="p-4 border-t bg-white">
        <form onSubmit={handleSubmit} className="flex gap-2">
          <div className="flex-1">
            <Input
              type="text"
              placeholder="메시지를 입력하세요..."
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              disabled={isLoading}
              className="!border-gray-300 focus:!border-blue-500"
              labelProps={{
                className: 'hidden',
              }}
              containerProps={{
                className: 'min-w-0',
              }}
            />
          </div>
          <IconButton
            type="submit"
            color="blue"
            disabled={!inputValue.trim() || isLoading}
          >
            <PaperAirplaneIcon className="h-5 w-5" />
          </IconButton>
        </form>
      </div>
    </div>
  );
};

export default MainPage;
