import React, { useEffect, useState } from 'react';
import { Typography } from '@material-tailwind/react';
import api from '../lib/api';
import { fetchUserDocuments } from '../lib/documentApi';
import { useAuthStore } from '../stores/authStore';
import { PageHeader } from '../components/common/PageHeader';
import DocumentTable, { type DocumentItem } from '../components/documents/DocumentTable';
import AnnounceAttachmentTable from '../components/documents/AnnounceAttachmentTable';
import type { Announce, Schedule } from '../types';

type TabKey = 'my-docs' | 'announce-attachments';

interface UserDocumentsResponse {
  items: DocumentItem[];
  total: number;
}

const LIMIT = 20;

const DocumentLibraryPage: React.FC = () => {
  const { user } = useAuthStore();
  const [activeTab, setActiveTab] = useState<TabKey>('my-docs');

  // 내 문서 상태
  const [docItems, setDocItems] = useState<DocumentItem[]>([]);
  const [docTotal, setDocTotal] = useState(0);
  const [docOffset, setDocOffset] = useState(0);
  const [docLoading, setDocLoading] = useState(false);
  const [docError, setDocError] = useState<string | null>(null);

  // 공고 첨부파일 상태
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [announces, setAnnounces] = useState<Record<number, Announce>>({});
  const [announceLoading, setAnnounceLoading] = useState(false);
  const [announceError, setAnnounceError] = useState<string | null>(null);

  const fetchDocs = async (offset: number) => {
    if (!user) return;
    setDocLoading(true);
    setDocError(null);
    try {
      const data: UserDocumentsResponse = await fetchUserDocuments(user.user_id, offset, LIMIT);
      setDocItems(data.items ?? []);
      setDocTotal(data.total ?? 0);
    } catch (err) {
      setDocError('문서를 불러오는데 실패했습니다.');
      console.error(err);
    } finally {
      setDocLoading(false);
    }
  };

  const fetchAnnounceAttachments = async () => {
    setAnnounceLoading(true);
    setAnnounceError(null);
    try {
      const schedulesRes = await api.get<Schedule[]>('/schedules');
      const fetchedSchedules: Schedule[] = Array.isArray(schedulesRes.data) ? schedulesRes.data : [];
      setSchedules(fetchedSchedules);

      const announceIds = Array.from(
        new Set(
          fetchedSchedules
            .filter((s) => s.announce_id != null)
            .map((s) => s.announce_id as number)
        )
      );

      if (announceIds.length === 0) {
        setAnnounces({});
        return;
      }

      const announceResults = await Promise.allSettled(
        announceIds.map((id) => api.get<Announce>(`/announces/${id}`))
      );

      const announceMap: Record<number, Announce> = {};
      announceResults.forEach((result, idx) => {
        if (result.status === 'fulfilled') {
          const announce = result.value.data;
          announceMap[announceIds[idx]] = announce;
        }
      });
      setAnnounces(announceMap);
    } catch (err) {
      setAnnounceError('공고 첨부파일을 불러오는데 실패했습니다.');
      console.error(err);
    } finally {
      setAnnounceLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'my-docs') {
      void fetchDocs(docOffset);
    }
  }, [activeTab, docOffset]);

  useEffect(() => {
    if (activeTab === 'announce-attachments') {
      void fetchAnnounceAttachments();
    }
  }, [activeTab]);

  const handleDocPageChange = (newOffset: number) => {
    setDocOffset(newOffset);
  };

  const handleDocRefresh = () => {
    void fetchDocs(docOffset);
  };

  const tabs: { key: TabKey; label: string }[] = [
    { key: 'my-docs', label: '내 문서' },
    { key: 'announce-attachments', label: '공고 첨부파일' },
  ];

  return (
    <div className="flex h-full min-h-0 flex-col">
      <PageHeader title="자료실" />

      <div className="min-h-0 flex-1 overflow-auto p-4 sm:p-6">
        <div className="space-y-4">
          {/* 탭 */}
          <div className="border-b border-gray-200">
            <div className="flex gap-0" role="tablist" aria-label="자료실 탭">
              {tabs.map((tab) => (
                <button
                  key={tab.key}
                  type="button"
                  role="tab"
                  aria-selected={activeTab === tab.key}
                  aria-controls={`tabpanel-${tab.key}`}
                  onClick={() => setActiveTab(tab.key)}
                  className={`px-4 py-2 text-sm font-medium transition-colors ${
                    activeTab === tab.key
                      ? 'border-b-2 border-blue-600 text-blue-600'
                      : 'text-gray-600 hover:text-gray-900'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

          {/* 내 문서 탭 */}
          <div
            role="tabpanel"
            id="tabpanel-my-docs"
            aria-labelledby="tab-my-docs"
            hidden={activeTab !== 'my-docs'}
          >
            {docError ? (
              <div className="rounded-lg border border-red-200 bg-red-50 p-4">
                <Typography color="red" variant="small">
                  {docError}
                </Typography>
              </div>
            ) : (
              <DocumentTable
                items={docItems}
                total={docTotal}
                offset={docOffset}
                limit={LIMIT}
                loading={docLoading}
                onPageChange={handleDocPageChange}
                onRefresh={handleDocRefresh}
              />
            )}
          </div>

          {/* 공고 첨부파일 탭 */}
          <div
            role="tabpanel"
            id="tabpanel-announce-attachments"
            aria-labelledby="tab-announce-attachments"
            hidden={activeTab !== 'announce-attachments'}
          >
            {announceError ? (
              <div className="rounded-lg border border-red-200 bg-red-50 p-4">
                <Typography color="red" variant="small">
                  {announceError}
                </Typography>
              </div>
            ) : announceLoading ? (
              <div className="py-10 text-center">
                <Typography color="gray">불러오는 중...</Typography>
              </div>
            ) : (
              <AnnounceAttachmentTable schedules={schedules} announces={announces} />
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default DocumentLibraryPage;
