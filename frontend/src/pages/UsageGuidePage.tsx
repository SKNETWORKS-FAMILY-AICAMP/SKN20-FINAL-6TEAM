import React from 'react';
import {
  Card,
  CardBody,
  CardHeader,
  Typography,
  Accordion,
  AccordionHeader,
  AccordionBody,
  Stepper,
  Step,
  Button,
} from '@material-tailwind/react';
import {
  ChatBubbleLeftRightIcon,
  BuildingOfficeIcon,
  CalendarDaysIcon,
  DocumentTextIcon,
  SparklesIcon,
  RocketLaunchIcon,
  BellAlertIcon,
  UserGroupIcon,
} from '@heroicons/react/24/outline';
import { PageHeader } from '../components/common/PageHeader';
import { useNavigate } from 'react-router-dom';
import { useChatStore } from '../stores/chatStore';

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
] as const;

const FAQ_ITEMS = [
  {
    question: 'Bizi는 무엇인가요?',
    answer:
      'Bizi는 예비 창업자, 스타트업 CEO, 중소기업 대표를 위한 AI 기반 통합 경영 상담 챗봇입니다. 창업 절차, 세무, 노무, 법률, 지원사업 등 다양한 분야의 맞춤형 상담을 제공합니다.',
  },
  {
    question: '어떤 분야의 상담이 가능한가요?',
    answer:
      '창업 및 지원사업, 재무 및 세무, 인사 및 노무 3개 전문 도메인에 대한 상담이 가능합니다. 질문을 입력하면 AI가 자동으로 적절한 전문 에이전트를 선택하여 답변합니다.',
  },
  {
    question: '기업 프로필을 등록하면 어떤 장점이 있나요?',
    answer:
      '기업 프로필을 등록하면 업종, 기업 규모, 설립일 등의 정보를 바탕으로 더 정확한 맞춤형 상담과 지원사업 추천을 받으실 수 있습니다.',
  },
  {
    question: '문서 자동 생성 기능이 있나요?',
    answer:
      '네, 근로계약서, 사업계획서 등의 문서를 AI가 자동으로 생성해드립니다. 채팅에서 요청하시면 됩니다.',
  },
  {
    question: '일정 관리는 어떻게 이용하나요?',
    answer:
      '일정 관리 메뉴에서 세금 신고 마감일, 지원사업 접수 기한 등의 일정을 등록하고 관리할 수 있습니다. 마감일이 다가오면 D-7, D-3 알림을 받으실 수 있습니다.',
  },
] as const;

const STEP_ICONS = [
  SparklesIcon,
  ChatBubbleLeftRightIcon,
  BuildingOfficeIcon,
  CalendarDaysIcon,
  RocketLaunchIcon,
] as const;

const STEP_LABELS = ['Bizi 소개', '채팅 사용법', '상담 분야', '추가 기능', '시작하기'] as const;

const EXPERT_DOMAINS = [
  { icon: BuildingOfficeIcon, label: '창업 및 지원사업', color: 'text-blue-500', bg: 'bg-blue-50' },
  { icon: DocumentTextIcon, label: '재무 및 세무', color: 'text-green-500', bg: 'bg-green-50' },
  { icon: UserGroupIcon, label: '인사 및 노무', color: 'text-purple-500', bg: 'bg-purple-50' },
  { icon: DocumentTextIcon, label: '법률 상담', color: 'text-amber-500', bg: 'bg-amber-50' },
];

const CHAT_STEPS = [
  { num: '1', text: '채팅 페이지에서 궁금한 내용이나 고민을 자유롭게 입력하세요.' },
  { num: '2', text: 'AI가 질문을 분석하여 적절한 전문 에이전트가 자동으로 답변합니다.' },
  { num: '3', text: '빠른 질문 버튼을 이용하면 자주 묻는 질문을 바로 확인할 수 있습니다.' },
  { num: '4', text: '기업 프로필을 등록하면 더 정확한 맞춤형 상담이 가능합니다.' },
];

const EXTRA_FEATURES = [
  {
    icon: BuildingOfficeIcon,
    title: '기업 프로필 등록',
    color: 'text-blue-500',
    bg: 'bg-blue-50',
    description: '업종, 기업 규모, 설립일 등을 등록하면 맞춤형 상담과 지원사업 추천을 받을 수 있습니다.',
  },
  {
    icon: CalendarDaysIcon,
    title: '일정 관리',
    color: 'text-green-500',
    bg: 'bg-green-50',
    description: '세금 신고 마감일, 지원사업 접수 기한 등 중요한 일정을 등록하고 관리할 수 있습니다.',
  },
  {
    icon: DocumentTextIcon,
    title: '문서 자동 생성',
    color: 'text-purple-500',
    bg: 'bg-purple-50',
    description: '근로계약서, 사업계획서 등의 문서를 AI가 자동으로 생성해드립니다.',
  },
  {
    icon: BellAlertIcon,
    title: '알림 설정',
    color: 'text-amber-500',
    bg: 'bg-amber-50',
    description: '마감일 D-7, D-3 알림으로 중요한 일정을 놓치지 않도록 도와드립니다.',
  },
];

/* ──────────────────── Step content components ──────────────────── */

function StepIntro() {
  return (
    <Card className="border border-gray-200 shadow-sm">
      <CardBody className="p-5 sm:p-6">
        <Typography variant="h5" className="mb-3 !text-gray-900">
          Bizi에 오신 것을 환영합니다
        </Typography>
        <Typography variant="small" className="mb-5 leading-relaxed !text-gray-700">
          Bizi는 예비 창업자, 스타트업 CEO, 중소기업 대표를 위한 AI 기반 통합 경영 상담 챗봇입니다.
          아래 4개 전문 분야에서 맞춤형 상담을 제공합니다.
        </Typography>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {EXPERT_DOMAINS.map((d) => (
            <div key={d.label} className={`flex flex-col items-center gap-2 rounded-lg ${d.bg} p-4`}>
              <d.icon className={`h-7 w-7 ${d.color}`} />
              <Typography variant="small" className="text-center font-medium !text-gray-800">
                {d.label}
              </Typography>
            </div>
          ))}
        </div>
      </CardBody>
    </Card>
  );
}

function StepChatUsage() {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {CHAT_STEPS.map((s) => (
        <Card key={s.num} className="border border-gray-200 shadow-sm">
          <CardBody className="flex items-start gap-3 p-4">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-blue-500 text-sm font-bold text-white">
              {s.num}
            </div>
            <Typography variant="small" className="leading-relaxed !text-gray-700">
              {s.text}
            </Typography>
          </CardBody>
        </Card>
      ))}
    </div>
  );
}

function StepDomains() {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {DOMAIN_SECTIONS.map((section) => (
        <Card key={section.title} className="border border-gray-200 shadow-sm">
          <CardBody className="h-full p-4">
            <div className="mb-3 flex items-center gap-2">
              <div className="rounded-lg bg-gray-50 p-2">
                <section.icon className={`h-5 w-5 ${section.color}`} />
              </div>
              <Typography variant="h6" color="blue-gray" className="!text-gray-900">
                {section.title}
              </Typography>
            </div>
            <Typography
              variant="small"
              color="gray"
              className="mb-4 min-h-[3rem] leading-relaxed !text-gray-700"
            >
              {section.description}
            </Typography>
            <Typography variant="small" className="mb-2 font-semibold !text-gray-800">
              질문 예시:
            </Typography>
            <ul className="space-y-1.5">
              {section.examples.map((example) => (
                <li key={example} className="flex items-start gap-2">
                  <span className="mt-[0.45rem] h-1 w-1 rounded-full bg-gray-400" aria-hidden />
                  <Typography
                    variant="small"
                    color="gray"
                    className="guide-example-text guide-soft-italic text-xs leading-relaxed font-normal !text-[#5b5b5b]"
                  >
                    {example}
                  </Typography>
                </li>
              ))}
            </ul>
          </CardBody>
        </Card>
      ))}
    </div>
  );
}

function StepExtraFeatures() {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {EXTRA_FEATURES.map((f) => (
        <Card key={f.title} className="border border-gray-200 shadow-sm">
          <CardBody className="p-4">
            <div className="mb-2 flex items-center gap-2">
              <div className={`rounded-lg ${f.bg} p-2`}>
                <f.icon className={`h-5 w-5 ${f.color}`} />
              </div>
              <Typography variant="h6" className="!text-gray-900">
                {f.title}
              </Typography>
            </div>
            <Typography variant="small" className="leading-relaxed !text-gray-700">
              {f.description}
            </Typography>
          </CardBody>
        </Card>
      ))}
    </div>
  );
}

function StepGetStarted({ onStart, onPrev }: { onStart: () => void; onPrev: () => void }) {
  const [openAccordion, setOpenAccordion] = React.useState<number>(-1);

  return (
    <div className="space-y-4">
      <Card className="overflow-hidden border border-gray-200 shadow-sm">
        <CardHeader
          floated={false}
          shadow={false}
          color="transparent"
          className="m-0 rounded-none border-b border-gray-200 px-4 py-3"
        >
          <Typography variant="h6" className="!text-gray-900">
            자주 묻는 질문
          </Typography>
        </CardHeader>
        <CardBody className="p-0">
          {FAQ_ITEMS.map((item, index) => (
            <Accordion
              key={index}
              open={openAccordion === index}
              className="border-b border-gray-200 px-4 last:border-b-0"
            >
              <AccordionHeader
                onClick={() => setOpenAccordion(openAccordion === index ? -1 : index)}
                className="py-3 text-sm font-medium !text-gray-800"
              >
                {item.question}
              </AccordionHeader>
              <AccordionBody className="guide-example-text pt-3 text-sm leading-relaxed font-normal !text-[#5b5b5b]">
                {item.answer}
              </AccordionBody>
            </Accordion>
          ))}
        </CardBody>
      </Card>

      <div className="flex items-center justify-between">
        <Button
          onClick={onPrev}
          variant="outlined"
          className="border-gray-300 !text-gray-700"
          placeholder=""
          onPointerEnterCapture={() => {}}
          onPointerLeaveCapture={() => {}}
        >
          이전
        </Button>
        <Button
          size="lg"
          className="flex items-center gap-2 bg-blue-500 !text-white shadow-none hover:shadow-none hover:bg-blue-600 transition-colors duration-150"
          onClick={onStart}
          placeholder=""
          onPointerEnterCapture={() => {}}
          onPointerLeaveCapture={() => {}}
        >
          <ChatBubbleLeftRightIcon className="h-5 w-5 text-white" />
          지금 바로 상담 시작하기
        </Button>
      </div>
    </div>
  );
}

/* ──────────────────── Main page ──────────────────── */

const STEP_CONTENT = [StepIntro, StepChatUsage, StepDomains, StepExtraFeatures] as const;

const UsageGuidePage: React.FC = () => {
  const [activeStep, setActiveStep] = React.useState(0);
  const [isFirstStep, setIsFirstStep] = React.useState(true);
  const [isLastStep, setIsLastStep] = React.useState(false);
  const navigate = useNavigate();
  const createSession = useChatStore((s) => s.createSession);

  const handleStartChat = () => {
    createSession();
    navigate('/');
  };

  const handleNext = () => {
    if (isLastStep) {
      handleStartChat();
      return;
    }
    setActiveStep((cur) => cur + 1);
  };

  const handlePrev = () => {
    if (!isFirstStep) setActiveStep((cur) => cur - 1);
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <PageHeader
        title={'사용 설명서'}
        description={'Bizi 챗봇의 주요 기능과 사용 방법을 안내합니다.'}
      />

      <div className="usage-guide-black min-h-0 flex-1 overflow-auto p-4 sm:p-6">
        <div className="mx-auto max-w-4xl space-y-6">
          {/* Stepper indicator */}
          <div className="w-full px-2 sm:px-8">
            <Stepper
              activeStep={activeStep}
              isLastStep={(value) => setIsLastStep(value)}
              isFirstStep={(value) => setIsFirstStep(value)}
              lineClassName="bg-gray-300"
              activeLineClassName="bg-blue-500"
              placeholder=""
              onPointerEnterCapture={() => {}}
              onPointerLeaveCapture={() => {}}
            >
              {STEP_ICONS.map((Icon, i) => (
                <Step
                  key={i}
                  onClick={() => setActiveStep(i)}
                  className="cursor-pointer !bg-gray-300 !text-gray-600"
                  activeClassName="!bg-blue-500 !text-white"
                  completedClassName="!bg-blue-500 !text-white"
                  placeholder=""
                  onPointerEnterCapture={() => {}}
                  onPointerLeaveCapture={() => {}}
                >
                  <Icon className="h-5 w-5" />
                  <div className="absolute -bottom-[2rem] w-max text-center">
                    <Typography
                      variant="small"
                      className={`text-xs font-medium ${
                        activeStep === i ? '!text-blue-500' : '!text-gray-500'
                      }`}
                    >
                      {STEP_LABELS[i]}
                    </Typography>
                  </div>
                </Step>
              ))}
            </Stepper>
          </div>

          {/* Step content */}
          <div className="mt-10 pt-4">
            {activeStep < STEP_CONTENT.length ? (
              React.createElement(STEP_CONTENT[activeStep])
            ) : (
              <StepGetStarted onStart={handleStartChat} onPrev={handlePrev} />
            )}
          </div>

          {/* Navigation buttons (hidden on last step — buttons are inside StepGetStarted) */}
          {!isLastStep && (
            <div className="flex justify-between pb-4">
              {!isFirstStep ? (
                <Button
                  onClick={handlePrev}
                  variant="outlined"
                  className="border-gray-300 !text-gray-700"
                  placeholder=""
                  onPointerEnterCapture={() => {}}
                  onPointerLeaveCapture={() => {}}
                >
                  이전
                </Button>
              ) : (
                <div />
              )}
              <Button
                onClick={handleNext}
                className="bg-blue-500 !text-white shadow-none hover:shadow-none hover:bg-blue-600 transition-colors duration-150"
                placeholder=""
                onPointerEnterCapture={() => {}}
                onPointerLeaveCapture={() => {}}
              >
                다음
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default UsageGuidePage;
