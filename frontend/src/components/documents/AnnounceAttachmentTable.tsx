import React, { useState } from 'react';
import { Typography } from '@material-tailwind/react';
import { ArrowDownTrayIcon } from '@heroicons/react/24/outline';
import { getAnnounceDownloadUrl } from '../../lib/documentApi';
import { useToastStore } from '../../stores/toastStore';
import type { Announce, Schedule } from '../../types';

interface AnnounceWithSchedule {
  announce: Announce;
  schedule: Schedule;
}

interface AnnounceAttachmentTableProps {
  schedules: Schedule[];
  announces: Record<number, Announce>;
}

const formatDate = (dateStr?: string): string => {
  if (!dateStr) return '-';
  return dateStr.split('T')[0];
};

const AnnounceAttachmentTable: React.FC<AnnounceAttachmentTableProps> = ({
  schedules,
  announces,
}) => {
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const addToast = useToastStore((s) => s.addToast);

  const linkedItems: AnnounceWithSchedule[] = schedules
    .filter((s) => s.announce_id != null && announces[s.announce_id] != null)
    .map((s) => ({
      announce: announces[s.announce_id as number],
      schedule: s,
    }));

  const handleDownload = async (announceId: number, type: 'doc' | 'form') => {
    const key = `${announceId}-${type}`;
    setDownloadingId(key);
    try {
      const url = await getAnnounceDownloadUrl(announceId, type);
      try {
        const parsed = new URL(url);
        if (!['http:', 'https:'].includes(parsed.protocol)) throw new Error('invalid protocol');
      } catch {
        addToast({ type: 'error', message: '유효하지 않은 다운로드 URL입니다.' });
        return;
      }
      window.open(url, '_blank', 'noopener,noreferrer');
    } catch (err) {
      addToast({ type: 'error', message: '다운로드에 실패했습니다.' });
    } finally {
      setDownloadingId(null);
    }
  };

  if (linkedItems.length === 0) {
    return (
      <div className="py-10 text-center">
        <Typography color="gray">등록된 공고 첨부파일이 없습니다.</Typography>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200">
      <table className="w-full min-w-[600px] text-sm">
        <thead>
          <tr className="border-b border-gray-200 bg-gray-50">
            <th className="px-4 py-3 text-left font-medium text-gray-700">공고명</th>
            <th className="px-4 py-3 text-left font-medium text-gray-700">일정 시작일</th>
            <th className="px-4 py-3 text-left font-medium text-gray-700">공고문</th>
            <th className="px-4 py-3 text-left font-medium text-gray-700">신청양식</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {linkedItems.map(({ announce, schedule }) => {
            const docKey = `${announce.announce_id}-doc`;
            const formKey = `${announce.announce_id}-form`;

            return (
              <tr key={schedule.schedule_id} className="hover:bg-gray-50">
                <td className="max-w-[240px] px-4 py-3">
                  <Typography variant="small" className="font-medium !text-gray-900 line-clamp-2">
                    {announce.ann_name}
                  </Typography>
                  <Typography variant="small" className="!text-xs !text-gray-500">
                    {announce.organization || '-'}
                  </Typography>
                </td>
                <td className="px-4 py-3 text-gray-700">
                  {formatDate(schedule.start_date)}
                </td>
                <td className="px-4 py-3">
                  {announce.has_doc ? (
                    <button
                      type="button"
                      onClick={() => void handleDownload(announce.announce_id, 'doc')}
                      disabled={downloadingId === docKey}
                      className="inline-flex items-center gap-1 rounded-md border border-blue-300 bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-700 transition-colors hover:bg-blue-100 disabled:opacity-50"
                      aria-label={`${announce.ann_name} 공고문 다운로드`}
                    >
                      <ArrowDownTrayIcon className="h-3.5 w-3.5" />
                      공고문
                    </button>
                  ) : (
                    <span className="text-xs text-gray-400">없음</span>
                  )}
                </td>
                <td className="px-4 py-3">
                  {announce.has_form ? (
                    <button
                      type="button"
                      onClick={() => void handleDownload(announce.announce_id, 'form')}
                      disabled={downloadingId === formKey}
                      className="inline-flex items-center gap-1 rounded-md border border-green-300 bg-green-50 px-3 py-1.5 text-xs font-medium text-green-700 transition-colors hover:bg-green-100 disabled:opacity-50"
                      aria-label={`${announce.ann_name} 신청양식 다운로드`}
                    >
                      <ArrowDownTrayIcon className="h-3.5 w-3.5" />
                      신청양식
                    </button>
                  ) : (
                    <span className="text-xs text-gray-400">없음</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

export default AnnounceAttachmentTable;
