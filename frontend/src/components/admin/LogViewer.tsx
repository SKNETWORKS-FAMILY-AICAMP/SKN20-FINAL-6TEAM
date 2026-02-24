import React, { useEffect, useRef, useState } from 'react';
import { useAdminLogs } from '../../hooks/useAdminLogs';

const LEVEL_COLOR: Record<string, string> = {
  CRITICAL: 'text-red-400 font-bold',
  ERROR:    'text-red-400',
  WARNING:  'text-yellow-400',
  WARN:     'text-yellow-400',
  INFO:     'text-gray-300',
  DEBUG:    'text-gray-500',
};

/** JSON 로그 라인에서 레벨을 추출합니다. */
const parseLevel = (line: string): string => {
  try {
    const parsed = JSON.parse(line) as Record<string, unknown>;
    return String(parsed.level ?? 'INFO');
  } catch {
    if (line.includes('CRITICAL')) return 'CRITICAL';
    if (line.includes('ERROR'))    return 'ERROR';
    if (line.includes('WARNING') || line.includes('WARN')) return 'WARNING';
    if (line.includes('DEBUG'))    return 'DEBUG';
    return 'INFO';
  }
};

/** JSON 로그 라인을 읽기 쉬운 형식으로 변환합니다. */
const formatLine = (line: string): string => {
  try {
    const parsed = JSON.parse(line) as Record<string, unknown>;
    const ts = String(parsed.timestamp ?? '').substring(0, 19).replace('T', ' ');
    const level = String(parsed.level ?? '').padEnd(8);
    const logger = String(parsed.logger ?? '');
    const msg = String(parsed.message ?? line);
    return `${ts} ${level} [${logger}] ${msg}`;
  } catch {
    return line;
  }
};

/**
 * 실시간 로그 뷰어.
 * - backend / rag 선택 가능
 * - 자동 갱신 토글 (10초)
 * - JSON 로그 라인 파싱 및 레벨별 색상 표시
 */
const LogViewer: React.FC = () => {
  const [file, setFile] = useState<'backend' | 'rag'>('backend');
  const [autoRefresh, setAutoRefresh] = useState(true);
  const containerRef = useRef<HTMLDivElement>(null);

  const { data, isLoading, dataUpdatedAt } = useAdminLogs(file, autoRefresh);

  // 새 데이터 도착 시 스크롤을 상단(최신)으로 유지
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = 0;
    }
  }, [dataUpdatedAt]);

  const lastUpdate = dataUpdatedAt
    ? new Date(dataUpdatedAt).toLocaleTimeString('ko-KR')
    : null;

  return (
    <div className="space-y-3">
      {/* 컨트롤 바 */}
      <div className="flex flex-wrap items-center gap-3">
        <select
          value={file}
          onChange={(e) => setFile(e.target.value as 'backend' | 'rag')}
          className="border border-gray-300 rounded px-2 py-1 text-sm text-gray-700 focus:outline-none focus:ring-1 focus:ring-blue-400"
        >
          <option value="backend">Backend</option>
          <option value="rag">RAG</option>
        </select>

        <label className="flex items-center gap-1.5 text-sm text-gray-600 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={autoRefresh}
            onChange={(e) => setAutoRefresh(e.target.checked)}
            className="rounded"
          />
          자동 갱신 (10초)
        </label>

        {data && (
          <span className="text-xs text-gray-400">
            총 {data.total_lines.toLocaleString()}줄
          </span>
        )}

        {lastUpdate && (
          <span className="text-xs text-gray-400 ml-auto">
            갱신: {lastUpdate}
          </span>
        )}
      </div>

      {/* 로그 뷰어 */}
      <div
        ref={containerRef}
        className="bg-gray-900 text-gray-100 rounded-lg p-4 h-80 overflow-y-auto font-mono text-xs leading-relaxed"
      >
        {isLoading && !data ? (
          <div className="text-gray-400 text-center py-4">로딩 중...</div>
        ) : data?.lines.length ? (
          data.lines.map((line, i) => {
            const level = parseLevel(line);
            const color = LEVEL_COLOR[level] ?? 'text-gray-400';
            return (
              <div key={i} className={`${color} py-0.5 break-all`}>
                {formatLine(line)}
              </div>
            );
          })
        ) : (
          <div className="text-gray-500 text-center py-8">
            로그 파일이 없거나 비어 있습니다.
            <br />
            <span className="text-xs">
              /var/log/app/{file}.log 파일이 존재하는지 확인하세요.
            </span>
          </div>
        )}
      </div>
    </div>
  );
};

export default LogViewer;
