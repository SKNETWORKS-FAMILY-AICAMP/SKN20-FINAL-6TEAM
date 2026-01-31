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
export const GUEST_MESSAGE_LIMIT = 10;

// Region data: 시/도 → 시/군/구 mapping
export const REGION_DATA: Record<string, string[]> = {
  서울특별시: [
    '강남구', '강동구', '강북구', '강서구', '관악구', '광진구', '구로구', '금천구',
    '노원구', '도봉구', '동대문구', '동작구', '마포구', '서대문구', '서초구', '성동구',
    '성북구', '송파구', '양천구', '영등포구', '용산구', '은평구', '종로구', '중구', '중랑구',
  ],
  부산광역시: [
    '강서구', '금정구', '기장군', '남구', '동구', '동래구', '부산진구', '북구',
    '사상구', '사하구', '서구', '수영구', '연제구', '영도구', '중구', '해운대구',
  ],
  대구광역시: [
    '남구', '달서구', '달성군', '동구', '북구', '서구', '수성구', '중구',
  ],
  인천광역시: [
    '강화군', '계양구', '남동구', '동구', '미추홀구', '부평구', '서구', '연수구', '옹진군', '중구',
  ],
  광주광역시: ['광산구', '남구', '동구', '북구', '서구'],
  대전광역시: ['대덕구', '동구', '서구', '유성구', '중구'],
  울산광역시: ['남구', '동구', '북구', '울주군', '중구'],
  세종특별자치시: ['세종시'],
  경기도: [
    '가평군', '고양시', '과천시', '광명시', '광주시', '구리시', '군포시', '김포시',
    '남양주시', '동두천시', '부천시', '성남시', '수원시', '시흥시', '안산시', '안성시',
    '안양시', '양주시', '양평군', '여주시', '연천군', '오산시', '용인시', '의왕시',
    '의정부시', '이천시', '파주시', '평택시', '포천시', '하남시', '화성시',
  ],
  강원특별자치도: [
    '강릉시', '고성군', '동해시', '삼척시', '속초시', '양구군', '양양군', '영월군',
    '원주시', '인제군', '정선군', '철원군', '춘천시', '태백시', '평창군', '홍천군',
    '화천군', '횡성군',
  ],
  충청북도: [
    '괴산군', '단양군', '보은군', '영동군', '옥천군', '음성군', '제천시', '증평군',
    '진천군', '청주시', '충주시',
  ],
  충청남도: [
    '계룡시', '공주시', '금산군', '논산시', '당진시', '보령시', '부여군', '서산시',
    '서천군', '아산시', '예산군', '천안시', '청양군', '태안군', '홍성군',
  ],
  전북특별자치도: [
    '고창군', '군산시', '김제시', '남원시', '무주군', '부안군', '순창군', '완주군',
    '익산시', '임실군', '장수군', '전주시', '정읍시', '진안군',
  ],
  전라남도: [
    '강진군', '고흥군', '곡성군', '광양시', '구례군', '나주시', '담양군', '목포시',
    '무안군', '보성군', '순천시', '신안군', '여수시', '영광군', '영암군', '완도군',
    '장성군', '장흥군', '진도군', '함평군', '해남군', '화순군',
  ],
  경상북도: [
    '경산시', '경주시', '고령군', '구미시', '군위군', '김천시', '문경시', '봉화군',
    '상주시', '성주군', '안동시', '영덕군', '영양군', '영주시', '영천시', '예천군',
    '울릉군', '울진군', '의성군', '청도군', '청송군', '칠곡군', '포항시',
  ],
  경상남도: [
    '거제시', '거창군', '고성군', '김해시', '남해군', '밀양시', '사천시', '산청군',
    '양산시', '의령군', '진주시', '창녕군', '창원시', '통영시', '하동군', '함안군',
    '함양군', '합천군',
  ],
  제주특별자치도: ['제주시', '서귀포시'],
};

export const PROVINCES = Object.keys(REGION_DATA);

// Company status for unified company form
export const COMPANY_STATUS = {
  PREPARING: '준비 중',
  OPERATING: '운영 중',
} as const;

export type CompanyStatusKey = keyof typeof COMPANY_STATUS;
