/**
 * AI 응답에서 [답변 근거] 마크다운 섹션을 제거합니다.
 * 구조화된 sources 데이터가 있을 때만 사용하여 중복 표시를 방지합니다.
 */
export function stripSourcesSection(content: string): string {
  const pattern = /\n---\n\*?\*?\[답변 근거\]\*?\*?[\s\S]*$/;
  return content.replace(pattern, '').trimEnd();
}

/**
 * HTTP 환경(비보안 컨텍스트)에서도 동작하는 UUID 생성 함수
 * crypto.randomUUID()는 HTTPS/localhost에서만 사용 가능
 */
export function generateId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}
