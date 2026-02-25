import React, { useState, useEffect } from 'react';
import api from '../lib/api';
import type {
  AdminHistoryListResponse,
  AdminHistoryDetail,
  AdminHistoryFilters,
} from '../types';
import { HistoryFilterBar } from '../components/admin/HistoryFilterBar';
import { HistoryTable } from '../components/admin/HistoryTable';
import { HistoryDetailModal } from '../components/admin/HistoryDetailModal';
import { PageHeader } from '../components/common/PageHeader';

const AdminLogPage: React.FC = () => {
  const [data, setData] = useState<AdminHistoryListResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<AdminHistoryFilters>({
    page: 1,
    page_size: 10,
  });
  const [selectedHistory, setSelectedHistory] = useState<AdminHistoryDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const fetchHistories = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      Object.entries(filters).forEach(([key, value]) => {
        if (value !== undefined && value !== '') {
          params.append(key, String(value));
        }
      });
      const response = await api.get<AdminHistoryListResponse>(
        `/admin/histories?${params.toString()}`
      );
      setData(response.data);
    } catch (err) {
      setError('상담 이력을 불러오는데 실패했습니다.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const fetchHistoryDetail = async (historyId: number) => {
    setDetailLoading(true);
    try {
      const response = await api.get<AdminHistoryDetail>(`/admin/histories/${historyId}`);
      setSelectedHistory(response.data);
    } catch (err) {
      console.error(err);
    } finally {
      setDetailLoading(false);
    }
  };

  useEffect(() => {
    fetchHistories();
  }, [filters.page]);

  const handleSearch = () => {
    setFilters((prev) => ({ ...prev, page: 1 }));
    fetchHistories();
  };

  const handlePageChange = (newPage: number) => {
    setFilters((prev) => ({ ...prev, page: newPage }));
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <PageHeader
        title={'\uC0C1\uB2F4 \uB85C\uADF8'}
      />

      <div className="min-h-0 flex-1 overflow-auto p-4 sm:p-6">
        <div className="space-y-4">
          <HistoryFilterBar
            filters={filters}
            onFiltersChange={setFilters}
            onSearch={handleSearch}
          />

          <HistoryTable
            data={data}
            loading={loading}
            error={error}
            onRowClick={fetchHistoryDetail}
            onPageChange={handlePageChange}
          />

          <HistoryDetailModal
            history={selectedHistory}
            loading={detailLoading}
            onClose={() => setSelectedHistory(null)}
          />
        </div>
      </div>
    </div>
  );
};

export default AdminLogPage;
