/** 날짜를 "2024년 1월 1일" 형태로 포맷합니다. */
export function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('ko-KR');
}

/** 날짜를 "2024년 1월 1일 오후 3:00:00" 형태로 포맷합니다. */
export function formatDateTime(dateStr: string): string {
  return new Date(dateStr).toLocaleString('ko-KR');
}

/** 날짜를 "2024년 1월 1일" (년/월/일 포함) 형태로 포맷합니다. */
export function formatDateLong(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('ko-KR', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
}
