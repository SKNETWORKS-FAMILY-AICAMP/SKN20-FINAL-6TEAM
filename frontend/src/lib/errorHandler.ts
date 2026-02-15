/**
 * API 에러 응답에서 사용자 표시용 메시지를 추출합니다.
 * axios 에러 형태의 response.data.detail 필드를 우선 사용하고,
 * 없으면 fallback 메시지를 반환합니다.
 */
export function extractErrorMessage(err: unknown, fallback: string): string {
  const error = err as { response?: { data?: { detail?: string } } };
  return error?.response?.data?.detail || fallback;
}
