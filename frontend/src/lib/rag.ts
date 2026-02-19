import axios from 'axios';
import type { RagStreamResponse, SourceReference } from '../types';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const RAG_ENABLED = import.meta.env.VITE_RAG_ENABLED !== 'false';
const RAG_STREAMING = import.meta.env.VITE_RAG_STREAMING !== 'false';

const ragApi = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
    'X-Requested-With': 'XMLHttpRequest',
  },
  withCredentials: true,
  timeout: 60000,
});

export const isRagEnabled = (): boolean => RAG_ENABLED;
export const isStreamingEnabled = (): boolean => RAG_STREAMING;

export const checkRagHealth = async (): Promise<boolean> => {
  if (!RAG_ENABLED) return false;
  try {
    const response = await ragApi.get('/rag/health', { timeout: 10000 });
    return response.data?.status === 'healthy' || response.data?.status === 'degraded';
  } catch {
    return false;
  }
};

export interface StreamCallbacks {
  onToken: (token: string) => void;
  onSource: (source: SourceReference) => void;
  onDone: (metadata: RagStreamResponse['metadata']) => void;
  onError: (error: string) => void;
}

/**
 * RAG 스트리밍 채팅 API 호출 (SSE) — Backend 프록시 경유
 */
export const streamChat = async (
  message: string,
  callbacks: StreamCallbacks,
  signal?: AbortSignal
): Promise<void> => {
  const response = await fetch(`${API_URL}/rag/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Requested-With': 'XMLHttpRequest',
    },
    credentials: 'include',
    body: JSON.stringify({ message }),
    signal,
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error('Response body is not readable');
  }

  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const jsonStr = line.slice(6).trim();
          if (!jsonStr) continue;

          try {
            const event: RagStreamResponse = JSON.parse(jsonStr);

            switch (event.type) {
              case 'token':
                if (event.content) {
                  callbacks.onToken(event.content);
                }
                break;
              case 'source':
                if (event.metadata) {
                  callbacks.onSource({
                    title: event.metadata.title || '',
                    source: event.metadata.source || '',
                    url: event.metadata.url || '',
                  });
                }
                break;
              case 'done':
                callbacks.onDone(event.metadata);
                break;
              case 'error':
                callbacks.onError(event.content || 'Unknown error');
                break;
            }
          } catch {
            // JSON 파싱 실패 무시
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
};

export default ragApi;
