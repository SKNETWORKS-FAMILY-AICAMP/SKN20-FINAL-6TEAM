import { useCallback } from 'react';
import { useChatStore } from '../stores/chatStore';
import { useAuthStore } from '../stores/authStore';
import ragApi from '../lib/rag';
import api from '../lib/api';
import type { ChatMessage, AgentCode, RagChatResponse } from '../types';
import { GUEST_MESSAGE_LIMIT } from '../lib/constants';

// Flag to switch between mock and RAG responses
const USE_RAG = false;

const ERROR_MESSAGE = '죄송합니다. 응답을 생성하는 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.';
const GUEST_LIMIT_MESSAGE = '무료 체험 메시지를 모두 사용했습니다. 로그인하시면 무제한으로 상담을 이용할 수 있습니다.';

export const useChat = () => {
  const { addMessage, setLoading, isLoading, lastHistoryId, setLastHistoryId, guestMessageCount, incrementGuestCount } = useChatStore();
  const { isAuthenticated } = useAuthStore();

  const sendMessage = useCallback(
    async (message: string) => {
      if (!message.trim() || isLoading) return;

      // Guest message limit check
      if (!isAuthenticated && guestMessageCount >= GUEST_MESSAGE_LIMIT) {
        const limitMessage: ChatMessage = {
          id: Date.now().toString(),
          type: 'assistant',
          content: GUEST_LIMIT_MESSAGE,
          agent_code: 'A0000001',
          timestamp: new Date(),
        };
        addMessage(limitMessage);
        return;
      }

      // Add user message
      const userMessage: ChatMessage = {
        id: Date.now().toString(),
        type: 'user',
        content: message,
        timestamp: new Date(),
      };
      addMessage(userMessage);
      setLoading(true);

      try {
        let response: string;
        let agentCode: AgentCode;

        if (USE_RAG) {
          // RAG API call
          const ragResponse = await ragApi.post<RagChatResponse>('/api/chat', {
            message,
          });
          response = ragResponse.data.response;
          agentCode = ragResponse.data.agent_code;
        } else {
          // Mock response
          const mockResult = await getMockResponse(message);
          response = mockResult.response;
          agentCode = mockResult.agent_code;
        }

        const assistantMessage: ChatMessage = {
          id: (Date.now() + 1).toString(),
          type: 'assistant',
          content: response,
          agent_code: agentCode,
          timestamp: new Date(),
        };
        addMessage(assistantMessage);

        // Save to backend history if authenticated
        if (isAuthenticated) {
          try {
            const historyResponse = await api.post('/histories', {
              agent_code: agentCode,
              question: message,
              answer: response,
              parent_history_id: lastHistoryId,
            });
            setLastHistoryId(historyResponse.data.history_id);
          } catch {
            // History save failure is non-critical
          }
        } else {
          incrementGuestCount();
        }
      } catch {
        const errorMessage: ChatMessage = {
          id: (Date.now() + 1).toString(),
          type: 'assistant',
          content: ERROR_MESSAGE,
          agent_code: 'A0000001',
          timestamp: new Date(),
        };
        addMessage(errorMessage);
      } finally {
        setLoading(false);
      }
    },
    [addMessage, setLoading, isLoading, isAuthenticated, lastHistoryId, setLastHistoryId, guestMessageCount, incrementGuestCount]
  );

  return { sendMessage, isLoading };
};

// Mock response generator
async function getMockResponse(
  question: string
): Promise<{ response: string; agent_code: AgentCode }> {
  // Simulate network delay
  await new Promise((resolve) => setTimeout(resolve, 1000));

  if (question.includes('사업자') || question.includes('창업') || question.includes('법인')) {
    return {
      response: generateStartupResponse(question),
      agent_code: 'A0000001',
    };
  }
  if (question.includes('세금') || question.includes('세무') || question.includes('부가세') || question.includes('신고') || question.includes('회계')) {
    return {
      response: generateTaxResponse(question),
      agent_code: 'A0000002',
    };
  }
  if (question.includes('법률') || question.includes('계약') || question.includes('법') || question.includes('분쟁')) {
    return {
      response: generateLegalResponse(question),
      agent_code: 'A0000003',
    };
  }
  if (question.includes('직원') || question.includes('채용') || question.includes('노무') || question.includes('근로') || question.includes('퇴직')) {
    return {
      response: generateHRResponse(question),
      agent_code: 'A0000004',
    };
  }
  if (question.includes('지원') || question.includes('정부') || question.includes('보조금') || question.includes('정책')) {
    return {
      response: generateFundingResponse(question),
      agent_code: 'A0000005',
    };
  }
  if (question.includes('마케팅') || question.includes('홍보') || question.includes('브랜드') || question.includes('고객')) {
    return {
      response: generateMarketingResponse(question),
      agent_code: 'A0000006',
    };
  }

  return {
    response: '질문해 주셔서 감사합니다.\n\n해당 내용에 대해 분석 중입니다. Bizi는 창업, 세무, 노무, 법률, 지원사업, 마케팅 분야의 상담을 제공합니다.\n\n더 구체적인 질문을 해주시면 더욱 정확한 답변을 드릴 수 있습니다.',
    agent_code: 'A0000001',
  };
}

function generateStartupResponse(question: string): string {
  if (question.includes('사업자 등록')) {
    return '사업자 등록 절차를 안내해드립니다.\n\n1. 국세청 홈택스(www.hometax.go.kr)에서 온라인 신청\n2. 또는 관할 세무서 방문 신청\n\n필요 서류:\n- 사업자등록 신청서\n- 임대차계약서 사본 (사업장이 있는 경우)\n- 신분증 사본\n- 업종별 허가/등록/신고증 (해당 시)\n\n처리 기간: 보통 1~3일 소요\n\n추가 궁금한 사항이 있으시면 언제든지 물어보세요!';
  }
  if (question.includes('법인')) {
    return '법인 설립 절차를 안내해드립니다.\n\n1. 발기인 구성 및 정관 작성\n2. 주금 납입 (자본금 준비)\n3. 설립등기 신청 (관할 등기소)\n4. 사업자등록 (관할 세무서/홈택스)\n5. 4대보험 가입 신고\n\n법인 설립 시 최소 자본금 제한이 없어졌으나, 업종에 따라 최소 자본금이 있을 수 있습니다.\n\n법인 설립 비용: 등록면허세 + 교육세 + 법무사 수수료 등이 필요합니다.';
  }
  return '창업 절차를 안내해드리겠습니다.\n\n1. 사업 아이디어 구체화 및 사업계획서 작성\n2. 업종 및 사업 형태 결정 (개인/법인)\n3. 사업자 등록\n4. 사업장 확보 (임대차 계약)\n5. 인허가 취득 (필요 시)\n6. 4대보험 가입 (직원 채용 시)\n7. 사업 개시\n\n각 단계별 상세 안내가 필요하시면 추가 질문해주세요!';
}

function generateTaxResponse(question: string): string {
  if (question.includes('부가세') || question.includes('부가가치세')) {
    return '부가가치세 신고 안내입니다.\n\n신고 기간:\n- 1기 예정: 4월 1일 ~ 25일 (1~3월 거래분)\n- 1기 확정: 7월 1일 ~ 25일 (4~6월 거래분)\n- 2기 예정: 10월 1일 ~ 25일 (7~9월 거래분)\n- 2기 확정: 다음 해 1월 1일 ~ 25일 (10~12월 거래분)\n\n간이과세자는 연 1회 (1월) 신고합니다.\n\n홈택스에서 전자신고가 가능합니다.';
  }
  return '세무 관련 안내입니다.\n\n사업자가 알아야 할 주요 세금:\n1. 부가가치세 - 분기별 신고\n2. 종합소득세 - 매년 5월 신고\n3. 원천징수 - 매월 10일까지 신고/납부\n4. 지방소득세 - 소득세 신고 시 함께\n\n절세를 위해 증빙서류를 꼼꼼히 관리하시는 것이 중요합니다.';
}

function generateLegalResponse(question: string): string {
  return '법률 관련 안내입니다.\n\n사업 운영 시 주의해야 할 주요 법률 사항:\n\n1. 근로기준법 준수 (직원 고용 시)\n2. 개인정보보호법 (고객 정보 관리)\n3. 공정거래법 (거래 관계)\n4. 소비자보호법 (소비자 대상 사업)\n5. 지식재산권 (상표, 특허)\n\n구체적인 법률 문제가 있으시면 상세하게 질문해주세요.';
}

function generateHRResponse(question: string): string {
  if (question.includes('근로계약서')) {
    return '근로계약서 필수 기재 사항을 안내해드립니다.\n\n근로기준법 제17조에 따른 필수 항목:\n1. 임금 (구성항목, 계산방법, 지급방법)\n2. 소정근로시간\n3. 휴일\n4. 연차유급휴가\n5. 근무장소와 업무내용\n6. 근로계약기간 (기간제인 경우)\n\n근로계약서는 서면으로 작성하여 근로자에게 교부해야 합니다.\n미작성 시 과태료 500만원이 부과될 수 있습니다.';
  }
  if (question.includes('채용')) {
    return '직원 채용 시 필요한 절차입니다.\n\n1. 채용 공고 및 면접\n2. 근로계약서 작성 (필수)\n3. 4대보험 가입 신고 (입사일 기준 14일 이내)\n   - 국민연금, 건강보험, 고용보험, 산재보험\n4. 근로소득 원천징수 등록\n5. 취업규칙 작성 (상시 10인 이상)\n\n수습 기간을 두는 경우에도 근로계약서 작성 및 4대보험 가입은 필수입니다.';
  }
  return '인사/노무 관련 안내입니다.\n\n주요 노무 관리 사항:\n1. 근로계약서 작성 및 교부\n2. 4대보험 가입 및 관리\n3. 임금 지급 (매월 1회 이상, 정해진 날)\n4. 근로시간 관리 (주 52시간 상한)\n5. 연차휴가 관리\n6. 퇴직금 지급 (1년 이상 근무 시)\n\n추가 질문이 있으시면 말씀해주세요.';
}

function generateFundingResponse(question: string): string {
  return '정부 지원사업 안내입니다.\n\n주요 지원사업:\n1. 창업사관학교 - 예비/초기 창업자 대상\n2. 청년창업사관학교 - 만 39세 이하\n3. 소상공인 정책자금 - 소상공인 대상\n4. 창업성장기술개발 - 기술 기반 창업\n5. 중소기업 R&D 지원 - 기술개발 기업\n\n기업 프로필을 등록하시면 맞춤형 지원사업 추천이 가능합니다.\n\n자세한 정보는 기업마당(www.bizinfo.go.kr)에서 확인하실 수 있습니다.';
}

function generateMarketingResponse(question: string): string {
  return '마케팅 관련 안내입니다.\n\n중소기업/스타트업 마케팅 전략:\n1. SNS 마케팅 (인스타그램, 블로그 등)\n2. 검색엔진 최적화 (SEO)\n3. 콘텐츠 마케팅\n4. 정부 지원 마케팅 사업 활용\n5. 네트워킹 및 전시회 참여\n\n예산이 제한적인 경우 SNS와 콘텐츠 마케팅부터 시작하시는 것을 추천드립니다.\n\n구체적인 업종이나 상황을 말씀해주시면 더 맞춤형 조언을 드릴 수 있습니다.';
}
