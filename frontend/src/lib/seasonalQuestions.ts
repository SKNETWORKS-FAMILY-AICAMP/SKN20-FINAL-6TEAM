/**
 * 월별 시즌 질문
 * 세무/회계 마감일, 지원사업 시즌 등을 고려한 계절별 추천 질문
 */

interface QuickQuestion {
  label: string;
  question: string;
}

const SEASONAL_QUESTIONS: Record<number, QuickQuestion[]> = {
  // 1월: 부가세 확정신고 (1/25), 연말정산
  1: [
    { label: '부가세 신고', question: '부가가치세 확정신고 기한과 준비사항이 궁금합니다.' },
    { label: '연말정산', question: '직원 연말정산 절차와 필요 서류가 무엇인가요?' },
  ],
  // 2월: 사업장현황신고
  2: [
    { label: '4대보험 신고', question: '4대보험 보수총액 신고 방법을 알려주세요.' },
    { label: '근로계약 갱신', question: '연초 근로계약 갱신 시 주의사항이 있나요?' },
  ],
  // 3월: 법인세 신고 (3/31)
  3: [
    { label: '법인세 신고', question: '법인세 신고 마감이 다가오는데 준비해야 할 서류가 궁금합니다.' },
    { label: '정부지원사업', question: '상반기 정부 지원사업 공고 일정이 궁금합니다.' },
  ],
  // 4월: 부가세 예정신고 (4/25)
  4: [
    { label: '부가세 예정신고', question: '부가가치세 예정신고 대상과 방법이 궁금합니다.' },
    { label: '창업지원', question: '창업 초기 정부 지원금 신청 방법을 알려주세요.' },
  ],
  // 5월: 종합소득세 신고 (5/31)
  5: [
    { label: '종소세 신고', question: '종합소득세 신고 기한과 절세 방법이 궁금합니다.' },
    { label: '근로장려금', question: '근로장려금 신청 자격과 방법을 알려주세요.' },
  ],
  // 6월: 상반기 결산
  6: [
    { label: '상반기 결산', question: '상반기 재무제표 정리 방법이 궁금합니다.' },
    { label: '세금 절감', question: '하반기 세금 절감을 위해 지금 준비할 것이 있나요?' },
  ],
  // 7월: 부가세 확정신고 (7/25)
  7: [
    { label: '부가세 신고', question: '7월 부가가치세 확정신고 준비사항이 궁금합니다.' },
    { label: '여름휴가 관리', question: '직원 여름휴가 사용 관련 노무 규정이 궁금합니다.' },
  ],
  // 8월: 주주총회, 감사
  8: [
    { label: '법인 운영', question: '중소기업 정기 주주총회 개최 절차가 궁금합니다.' },
    { label: '인력채용', question: '하반기 채용 시 주의해야 할 노무 사항이 있나요?' },
  ],
  // 9월: 하반기 지원사업
  9: [
    { label: '하반기 지원사업', question: '하반기 중소기업 지원사업 공고 일정이 궁금합니다.' },
    { label: '추석 상여금', question: '추석 상여금 지급 시 원천징수 방법이 궁금합니다.' },
  ],
  // 10월: 부가세 예정신고 (10/25)
  10: [
    { label: '부가세 예정신고', question: '10월 부가가치세 예정신고 준비사항이 궁금합니다.' },
    { label: '연간 계획', question: '내년 사업계획 수립 시 고려할 세무 사항이 있나요?' },
  ],
  // 11월: 연말 준비
  11: [
    { label: '연말 세무', question: '연말 세금 신고 전 정리해야 할 사항이 궁금합니다.' },
    { label: '성과급 지급', question: '연말 성과급 지급 시 세금 처리 방법이 궁금합니다.' },
  ],
  // 12월: 연말정산 준비
  12: [
    { label: '연말정산 준비', question: '직원 연말정산 자료 수집 방법이 궁금합니다.' },
    { label: '결산 준비', question: '연간 결산 준비 체크리스트가 궁금합니다.' },
  ],
};

/**
 * 현재 월에 해당하는 계절별 질문을 반환합니다.
 */
export function getSeasonalQuestions(): QuickQuestion[] {
  const currentMonth = new Date().getMonth() + 1; // 1-12
  return SEASONAL_QUESTIONS[currentMonth] || SEASONAL_QUESTIONS[1];
}
