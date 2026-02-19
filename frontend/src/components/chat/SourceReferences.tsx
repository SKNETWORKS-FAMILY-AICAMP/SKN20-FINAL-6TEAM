import React, { useState } from 'react';
import { ChevronDownIcon, ChevronUpIcon, DocumentTextIcon } from '@heroicons/react/24/outline';
import type { SourceReference } from '../../types';

interface SourceReferencesProps {
  sources: SourceReference[];
}

export const SourceReferences: React.FC<SourceReferencesProps> = ({ sources }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  if (!sources || sources.length === 0) return null;

  // title + url 기준 중복 제거
  const uniqueSources = sources.filter(
    (s, i, arr) => arr.findIndex((x) => x.title === s.title && x.url === s.url) === i
  );

  return (
    <div className="mt-3 pt-2 border-t border-gray-200">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-blue-500 transition-colors"
      >
        <DocumentTextIcon className="h-3.5 w-3.5" />
        <span>답변 근거 {uniqueSources.length}건</span>
        {isExpanded ? (
          <ChevronUpIcon className="h-3 w-3" />
        ) : (
          <ChevronDownIcon className="h-3 w-3" />
        )}
      </button>
      {isExpanded && (
        <ul className="mt-2 space-y-1.5">
          {uniqueSources.map((source, index) => (
            <li key={index} className="flex items-start gap-2 text-xs">
              <span className="text-gray-400 mt-0.5 shrink-0">[{index + 1}]</span>
              <div className="min-w-0">
                {source.url ? (
                  <a
                    href={source.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-500 hover:text-blue-600 hover:underline break-words"
                    title={source.title}
                  >
                    {source.title
                      ? source.title.length > 60
                        ? source.title.slice(0, 60) + '...'
                        : source.title
                      : source.url}
                  </a>
                ) : (
                  <span className="text-gray-700 break-words">
                    {source.title || '제목 없음'}
                  </span>
                )}
                {source.source && (
                  <span className="ml-1.5 text-gray-400">({source.source})</span>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};
