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
import { PageHeader } from '../components/common/PageHeader';

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

const UsageGuidePage: React.FC = () => {
  const [openAccordion, setOpenAccordion] = React.useState<number>(-1);

  return (
    <div className="usage-guide-black flex h-full min-h-0 flex-col">
      <PageHeader
        title={'\uC0AC\uC6A9 \uC124\uBA85\uC11C'}
        description={'Bizi \uCC57\uBD07\uC758 \uC8FC\uC694 \uAE30\uB2A5\uACFC \uC0AC\uC6A9 \uBC29\uBC95\uC744 \uC548\uB0B4\uD569\uB2C8\uB2E4.'}
      />

      <div className="min-h-0 flex-1 overflow-auto p-4 sm:p-6">
        <div className="mx-auto max-w-6xl space-y-6">
          <section aria-label="시작하기 섹션" className="space-y-3">
            <div className="flex items-center gap-2">
              <div className="h-2 w-2 rounded-full bg-blue-500" />
              <Typography variant="h6" color="blue-gray" className="!text-gray-900">
                시작하기
              </Typography>
            </div>

            <Card className="border border-gray-200 shadow-sm">
              <CardBody className="p-4 sm:p-5">
                <div className="flex items-start gap-3">
                  <div className="space-y-2">
                    <Typography variant="small" color="gray" className="leading-relaxed !text-gray-700">
                      1. 채팅 페이지에서 궁금한 내용이나 고민을 자유롭게 입력하세요.
                    </Typography>
                    <Typography variant="small" color="gray" className="leading-relaxed !text-gray-700">
                      2. AI가 질문을 분석하여 적절한 전문 에이전트가 답변합니다.
                    </Typography>
                    <Typography variant="small" color="gray" className="leading-relaxed !text-gray-700">
                      3. 빠른 질문 버튼을 이용하면 자주 묻는 질문을 바로 확인할 수 있습니다.
                    </Typography>
                    <Typography variant="small" color="gray" className="leading-relaxed !text-gray-700">
                      4. 기업 프로필을 등록하면 더 정확한 맞춤형 상담이 가능합니다.
                    </Typography>
                  </div>
                </div>
              </CardBody>
            </Card>
          </section>

          <section aria-label="상담 분야 섹션" className="space-y-3">
            <div className="flex items-center gap-2">
              <div className="h-2 w-2 rounded-full bg-cyan-500" />
              <Typography variant="h6" color="blue-gray" className="!text-gray-900">
                상담 분야
              </Typography>
            </div>

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
          </section>

          <section aria-label="FAQ 섹션" className="space-y-3">
            <div className="flex items-center gap-2">
              <div className="h-2 w-2 rounded-full bg-green-500" />
              <Typography variant="h6" color="blue-gray" className="!text-gray-900">
                FAQ
              </Typography>
            </div>

            <Card className="overflow-hidden border border-gray-200 shadow-sm">
              <CardHeader
                floated={false}
                shadow={false}
                color="transparent"
                className="m-0 rounded-none border-b border-gray-200 px-4 py-3"
              >
                <div className="flex items-center gap-2">
                </div>
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
          </section>
        </div>
      </div>
    </div>
  );
};

export default UsageGuidePage;
