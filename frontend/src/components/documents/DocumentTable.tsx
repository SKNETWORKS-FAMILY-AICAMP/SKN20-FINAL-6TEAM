import React, { useState } from 'react';
import { Typography } from '@material-tailwind/react';
import { ArrowDownTrayIcon, TrashIcon } from '@heroicons/react/24/outline';
import { getDocumentDownloadUrl, deleteDocument } from '../../lib/documentApi';
import { useToastStore } from '../../stores/toastStore';
import { isHttpUrl } from '../../lib/utils';
import type { DocumentItem } from '../../types';

export type { DocumentItem };

const DOC_TYPE_LABELS: Record<string, string> = {
  labor_contract: '근로계약서',
  business_plan: '사업계획서',
  nda: '비밀유지계약서',
  service_agreement: '용역계약서',
  other: '기타',
};

interface DocumentTableProps {
  items: DocumentItem[];
  total: number;
  offset: number;
  limit: number;
  loading: boolean;
  onPageChange: (offset: number) => void;
  onRefresh: () => void;
}

const formatFileSize = (bytes?: number): string => {
  if (bytes == null) return '-';
  return `${Math.ceil(bytes / 1024)} KB`;
};

const formatDate = (dateStr?: string): string => {
  if (!dateStr) return '-';
  return dateStr.split('T')[0];
};

const DocumentTable: React.FC<DocumentTableProps> = ({
  items,
  total,
  offset,
  limit,
  loading,
  onPageChange,
  onRefresh,
}) => {
  const [actionLoadingId, setActionLoadingId] = useState<number | null>(null);
  const addToast = useToastStore((s) => s.addToast);

  const handleDownload = async (fileId: number) => {
    setActionLoadingId(fileId);
    try {
      const url = await getDocumentDownloadUrl(fileId);
      if (!isHttpUrl(url)) {
        addToast({ type: 'error', message: '유효하지 않은 다운로드 URL입니다.' });
        return;
      }
      window.open(url, '_blank', 'noopener,noreferrer');
    } catch (err) {
      addToast({ type: 'error', message: '다운로드에 실패했습니다.' });
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleDelete = async (fileId: number) => {
    if (!window.confirm('문서를 삭제하시겠습니까?')) return;
    setActionLoadingId(fileId);
    try {
      await deleteDocument(fileId);
      onRefresh();
    } catch (err) {
      addToast({ type: 'error', message: '삭제에 실패했습니다.' });
    } finally {
      setActionLoadingId(null);
    }
  };

  const totalPages = Math.ceil(total / limit);
  const currentPage = Math.floor(offset / limit) + 1;

  if (loading) {
    return (
      <div className="py-10 text-center">
        <Typography color="gray">불러오는 중...</Typography>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="py-10 text-center">
        <Typography color="gray">생성된 문서가 없습니다.</Typography>
      </div>
    );
  }

  return (
    <div>
      <div className="overflow-x-auto rounded-lg border border-gray-200">
        <table className="w-full min-w-[600px] text-sm">
          <thead>
            <tr className="border-b border-gray-200 bg-gray-50">
              <th className="px-4 py-3 text-left font-medium text-gray-700">파일명</th>
              <th className="px-4 py-3 text-left font-medium text-gray-700">문서유형</th>
              <th className="px-4 py-3 text-left font-medium text-gray-700">형식</th>
              <th className="px-4 py-3 text-left font-medium text-gray-700">크기</th>
              <th className="px-4 py-3 text-left font-medium text-gray-700">생성일</th>
              <th className="px-4 py-3 text-left font-medium text-gray-700">액션</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {items.map((item) => (
              <tr key={item.file_id} className="hover:bg-gray-50">
                <td className="max-w-[200px] truncate px-4 py-3 font-medium text-gray-900">
                  {item.file_name}
                </td>
                <td className="px-4 py-3 text-gray-700">
                  {item.doc_type ? (DOC_TYPE_LABELS[item.doc_type] ?? item.doc_type) : '-'}
                </td>
                <td className="px-4 py-3 text-gray-700">
                  {item.format ? item.format.toUpperCase() : '-'}
                </td>
                <td className="px-4 py-3 text-gray-700">{formatFileSize(item.file_size)}</td>
                <td className="px-4 py-3 text-gray-700">{formatDate(item.create_date)}</td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      onClick={() => void handleDownload(item.file_id)}
                      disabled={actionLoadingId === item.file_id}
                      className="inline-flex h-8 w-8 items-center justify-center rounded-md text-blue-600 transition-colors hover:bg-blue-50 disabled:opacity-50"
                      aria-label={`${item.file_name} 다운로드`}
                    >
                      <ArrowDownTrayIcon className="h-4 w-4" />
                    </button>
                    <button
                      type="button"
                      onClick={() => void handleDelete(item.file_id)}
                      disabled={actionLoadingId === item.file_id}
                      className="inline-flex h-8 w-8 items-center justify-center rounded-md text-red-500 transition-colors hover:bg-red-50 disabled:opacity-50"
                      aria-label={`${item.file_name} 삭제`}
                    >
                      <TrashIcon className="h-4 w-4" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="mt-4 flex items-center justify-between">
          <Typography variant="small" color="gray">
            전체 {total}개 중 {offset + 1}–{Math.min(offset + limit, total)}번
          </Typography>
          <div className="flex gap-1">
            <button
              type="button"
              onClick={() => onPageChange(Math.max(0, offset - limit))}
              disabled={offset === 0}
              className="rounded-md border border-gray-300 px-3 py-1 text-sm text-gray-700 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              이전
            </button>
            <span className="flex items-center px-3 text-sm text-gray-700">
              {currentPage} / {totalPages}
            </span>
            <button
              type="button"
              onClick={() => onPageChange(offset + limit)}
              disabled={offset + limit >= total}
              className="rounded-md border border-gray-300 px-3 py-1 text-sm text-gray-700 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              다음
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default DocumentTable;
