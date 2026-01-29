// Industry codes (B001-B021)
export const INDUSTRY_CODES: Record<string, string> = {
  B001: '음식점업',
  B002: '소매업',
  B003: '서비스업',
  B004: '제조업',
  B005: 'IT/소프트웨어',
  B006: '도매업',
  B007: '건설업',
  B008: '운수업',
  B009: '숙박업',
  B010: '교육서비스업',
  B011: '부동산업',
  B012: '금융/보험업',
  B013: '예술/스포츠/여가',
  B014: '전문/과학/기술',
  B015: '보건/사회복지',
  B016: '농업/임업/어업',
  B017: '광업',
  B018: '전기/가스/수도',
  B019: '환경/폐기물',
  B020: '출판/영상/통신',
  B021: '기타',
};

// Guest user situation types
export type GuestUserSituation = 'PRE_STARTUP' | 'NEW_STARTUP' | 'SME_CEO';

// Situation labels
export const SITUATION_LABELS: Record<GuestUserSituation, string> = {
  PRE_STARTUP: '예비 창업자',
  NEW_STARTUP: '신규 창업자',
  SME_CEO: '중소기업 CEO',
};

// Situation descriptions
export const SITUATION_DESCRIPTIONS: Record<GuestUserSituation, string> = {
  PRE_STARTUP: '창업을 준비하고 계신 분',
  NEW_STARTUP: '최근 사업을 시작하신 분',
  SME_CEO: '기업을 운영하고 계신 분',
};

// Guest quick questions per situation
export const GUEST_QUICK_QUESTIONS: Record<GuestUserSituation, Array<{ label: string; question: string }>> = {
  PRE_STARTUP: [
    { label: '사업자 등록 방법', question: '사업자 등록은 어떻게 하나요?' },
    { label: '창업 절차 안내', question: '창업 절차를 처음부터 알려주세요.' },
    { label: '창업 지원금', question: '예비 창업자가 받을 수 있는 지원금이 있나요?' },
    { label: '업종 선택 가이드', question: '업종을 어떻게 선택해야 하나요?' },
  ],
  NEW_STARTUP: [
    { label: '세금 신고 일정', question: '신규 사업자의 세금 신고 일정을 알려주세요.' },
    { label: '직원 채용 절차', question: '직원을 처음 채용할 때 어떤 절차가 필요한가요?' },
    { label: '정부 지원사업', question: '신규 창업자에게 맞는 정부 지원사업을 추천해주세요.' },
    { label: '사업계획서 작성', question: '사업계획서는 어떻게 작성하나요?' },
  ],
  SME_CEO: [
    { label: '노무 관리', question: '직원 노무 관리에서 주의해야 할 사항은 무엇인가요?' },
    { label: '세무 최적화', question: '중소기업의 세무 최적화 방법을 알려주세요.' },
    { label: '법률 리스크', question: '기업 운영 시 주의해야 할 법률 리스크가 있나요?' },
    { label: '지원사업 추천', question: '우리 회사에 맞는 정부 지원사업을 추천해주세요.' },
  ],
};

// Authenticated user quick questions per type_code
export const USER_QUICK_QUESTIONS: Record<string, Array<{ label: string; question: string }>> = {
  U001: [
    { label: '사업자 등록', question: '사업자 등록은 어떻게 하나요?' },
    { label: '부가세 신고', question: '부가가치세 신고는 언제 해야 하나요?' },
    { label: '직원 채용', question: '직원을 채용할 때 필요한 절차가 뭔가요?' },
    { label: '지원사업 찾기', question: '우리 회사에 맞는 정부 지원사업을 추천해주세요.' },
  ],
  U002: [
    { label: '사업자 등록 방법', question: '사업자 등록은 어떻게 하나요?' },
    { label: '법인 설립 절차', question: '법인 설립 절차를 알려주세요.' },
    { label: '창업 지원금', question: '예비 창업자가 받을 수 있는 지원금이 있나요?' },
    { label: '업종 선택 가이드', question: '업종을 어떻게 선택해야 하나요?' },
    { label: '사업계획서 작성', question: '사업계획서는 어떻게 작성하나요?' },
    { label: '근로계약서 작성', question: '근로계약서는 어떻게 작성하나요?' },
  ],
  U003: [
    { label: '부가세 신고', question: '부가가치세 신고는 언제 해야 하나요?' },
    { label: '직원 채용 절차', question: '직원을 채용할 때 필요한 절차가 뭔가요?' },
    { label: '노무 관리', question: '직원 노무 관리에서 주의해야 할 사항은 무엇인가요?' },
    { label: '세무 최적화', question: '중소기업의 세무 최적화 방법을 알려주세요.' },
    { label: '지원사업 찾기', question: '우리 회사에 맞는 정부 지원사업을 추천해주세요.' },
    { label: '근로계약서 작성', question: '근로계약서는 어떻게 작성하나요?' },
  ],
};

// Max guest messages before login prompt
export const GUEST_MESSAGE_LIMIT = 3;
