import React from 'react';
import {
  Card,
  CardBody,
  CardHeader,
  Typography,
  Accordion,
  AccordionHeader,
  AccordionBody,
} from '@material-tailwind/react';
import {
  ChatBubbleLeftRightIcon,
  BuildingOfficeIcon,
  CalendarDaysIcon,
  DocumentTextIcon,
  QuestionMarkCircleIcon,
} from '@heroicons/react/24/outline';

const DOMAIN_SECTIONS = [
  {
    title: '창업 및 지원사업 상담',
    icon: BuildingOfficeIcon,
    color: 'text-blue-500',
    description: '사업자 등록, 창업 절차, 정부 지원사업 추천 등 창업 전반에 관한 상담을 제공합니다.',
    examples: [
      '사업자 등록은 어떻게 하나요?',
      '예비 창업자가 받을 수 있는 지원사업을 알려주세요.',
      '법인 설립 절차를 알려주세요.',
    ],
  },
  {
    title: '재무 및 세무 상담',
    icon: DocumentTextIcon,
    color: 'text-green-500',
    description: '세금 신고, 회계 처리, 재무 관리 등 세무 전반에 관한 상담을 제공합니다.',
    examples: [
      '부가가치세 신고 기간은 언제인가요?',
      '중소기업의 세무 최적화 방법을 알려주세요.',
      '법인세 절세 방법이 있나요?',
    ],
  },
  {
    title: '인사 및 노무 상담',
    icon: CalendarDaysIcon,
    color: 'text-purple-500',
    description: '근로계약, 4대보험, 인사 관리 등 노무 전반에 관한 상담을 제공합니다.',
    examples: [
      '근로계약서 작성 시 필수 항목은 무엇인가요?',
      '4대보험 가입 절차를 알려주세요.',
      '퇴직금 계산 방법을 알려주세요.',
    ],
  },
];

const FAQ_ITEMS = [
  {
    question: 'Bizi는 무엇인가요?',
    answer: 'Bizi는 예비 창업자, 스타트업 CEO, 중소기업 대표를 위한 AI 기반 통합 경영 상담 챗봇입니다. 창업 절차, 세무, 노무, 법률, 지원사업 등 다양한 분야의 맞춤형 상담을 제공합니다.',
  },
  {
    question: '어떤 분야의 상담이 가능한가요?',
    answer: '창업 및 지원사업, 재무 및 세무, 인사 및 노무 3개 전문 도메인에 대한 상담이 가능합니다. 질문을 입력하면 AI가 자동으로 적절한 전문 에이전트를 선택하여 답변합니다.',
  },
  {
    question: '기업 프로필을 등록하면 어떤 장점이 있나요?',
    answer: '기업 프로필을 등록하면 업종, 기업 규모, 설립일 등의 정보를 바탕으로 더 정확한 맞춤형 상담과 지원사업 추천을 받으실 수 있습니다.',
  },
  {
    question: '문서 자동 생성 기능이 있나요?',
    answer: '네, 근로계약서, 사업계획서 등의 문서를 AI가 자동으로 생성해드립니다. 채팅에서 요청하시면 됩니다.',
  },
  {
    question: '일정 관리는 어떻게 이용하나요?',
    answer: '일정 관리 메뉴에서 세금 신고 마감일, 지원사업 접수 기한 등의 일정을 등록하고 관리할 수 있습니다. 마감일이 다가오면 D-7, D-3 알림을 받으실 수 있습니다.',
  },
];

const UsageGuidePage: React.FC = () => {
  const [openAccordion, setOpenAccordion] = React.useState<number>(0);

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <Typography variant="h4" color="blue-gray" className="mb-2 !text-gray-900">
        사용 설명서
      </Typography>
      <Typography variant="paragraph" color="gray" className="mb-6 !text-gray-700">
        Bizi 챗봇의 주요 기능과 사용 방법을 안내합니다.
      </Typography>

      {/* Getting Started */}
      <Card className="mb-6">
        <CardHeader floated={false} shadow={false} className="rounded-none">
          <div className="flex items-center gap-2">
            <ChatBubbleLeftRightIcon className="h-6 w-6 text-blue-500" />
            <Typography variant="h5" color="blue-gray" className="!text-gray-900">
              시작하기
            </Typography>
          </div>
        </CardHeader>
        <CardBody className="pt-0">
          <div className="space-y-3">
            <Typography variant="small" color="gray" className="!text-gray-700">
              1. 채팅 페이지에서 궁금한 내용을 자유롭게 입력하세요.
            </Typography>
            <Typography variant="small" color="gray" className="!text-gray-700">
              2. AI가 질문을 분석하여 적절한 전문 에이전트가 답변합니다.
            </Typography>
            <Typography variant="small" color="gray" className="!text-gray-700">
              3. 빠른 질문 버튼을 이용하면 자주 묻는 질문을 바로 할 수 있습니다.
            </Typography>
            <Typography variant="small" color="gray" className="!text-gray-700">
              4. 기업 프로필을 등록하면 더 정확한 맞춤형 상담이 가능합니다.
            </Typography>
          </div>
        </CardBody>
      </Card>

      {/* Domain Sections */}
      <Typography variant="h5" color="blue-gray" className="!text-gray-900" className="mb-4">
        상담 도메인
      </Typography>
      <div className="grid gap-4 md:grid-cols-3 mb-6">
        {DOMAIN_SECTIONS.map((section) => (
          <Card key={section.title}>
            <CardBody>
              <div className="flex items-center gap-2 mb-3">
                <section.icon className={`h-6 w-6 ${section.color}`} />
                <Typography variant="h6" color="blue-gray" className="!text-gray-900">
                  {section.title}
                </Typography>
              </div>
              <Typography variant="small" color="gray" className="mb-3 !text-gray-700">
                {section.description}
              </Typography>
              <Typography variant="small" className="font-semibold text-gray-700 mb-2">
                질문 예시:
              </Typography>
              <ul className="space-y-1">
                {section.examples.map((example) => (
                  <li key={example}>
                    <Typography variant="small" color="gray" className="text-xs !text-gray-700">
                      - {example}
                    </Typography>
                  </li>
                ))}
              </ul>
            </CardBody>
          </Card>
        ))}
      </div>

      {/* FAQ */}
      <Card>
        <CardHeader floated={false} shadow={false} className="rounded-none">
          <div className="flex items-center gap-2">
            <QuestionMarkCircleIcon className="h-6 w-6 text-blue-500" />
            <Typography variant="h5" color="blue-gray" className="!text-gray-900">
              자주 묻는 질문
            </Typography>
          </div>
        </CardHeader>
        <CardBody className="pt-0">
          {FAQ_ITEMS.map((item, index) => (
            <Accordion
              key={index}
              open={openAccordion === index}
              className="border-b last:border-b-0"
            >
              <AccordionHeader
                onClick={() => setOpenAccordion(openAccordion === index ? -1 : index)}
                className="text-sm py-3"
              >
                {item.question}
              </AccordionHeader>
              <AccordionBody className="text-sm text-gray-600">
                {item.answer}
              </AccordionBody>
            </Accordion>
          ))}
        </CardBody>
      </Card>
    </div>
  );
};

export default UsageGuidePage;
