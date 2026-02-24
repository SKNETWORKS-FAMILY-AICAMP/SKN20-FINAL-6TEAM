import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Card, CardBody, Typography } from '@material-tailwind/react';
import {
  NewspaperIcon,
  CalendarDaysIcon,
  MegaphoneIcon,
  BuildingOffice2Icon,
  ChevronLeftIcon,
  ChevronRightIcon,
} from '@heroicons/react/24/outline';
import api from '../../lib/api';
import type { Announce, Company, Schedule } from '../../types';

const formatDate = (dateStr: string | undefined): string => {
  if (!dateStr) return '-';
  return dateStr.split('T')[0];
};

const safeUrl = (url: string | undefined): string => {
  if (!url) return '#';
  try {
    const parsed = new URL(url);
    return ['http:', 'https:'].includes(parsed.protocol) ? url : '#';
  } catch {
    return '#';
  }
};

const ITEMS_PER_PAGE = 3;

interface CompanyDashboardProps {
  selectedCompany: Company | null;
}

export const CompanyDashboard: React.FC<CompanyDashboardProps> = ({ selectedCompany }) => {
  const [announces, setAnnounces] = useState<Announce[]>([]);
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [loadingAnnounces, setLoadingAnnounces] = useState(false);
  const [loadingSchedules, setLoadingSchedules] = useState(false);
  const [currentPage, setCurrentPage] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const totalPages = Math.max(1, Math.ceil(announces.length / ITEMS_PER_PAGE));
  const pagedAnnounces = announces.slice(currentPage * ITEMS_PER_PAGE, (currentPage + 1) * ITEMS_PER_PAGE);

  // totalPages를 ref로 관리하여 setInterval 클로저의 stale capture 방지
  const totalPagesRef = useRef(totalPages);
  totalPagesRef.current = totalPages;

  const resetTimer = useCallback(() => {
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = setInterval(() => {
      setCurrentPage((prev) => (prev + 1) % totalPagesRef.current);
    }, 15000);
  }, []);

  useEffect(() => {
    if (announces.length > ITEMS_PER_PAGE) {
      resetTimer();
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [currentPage, totalPages, announces.length]);

  useEffect(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setCurrentPage(0);
  }, [selectedCompany?.company_id]);


  useEffect(() => {
    if (!selectedCompany) return;

    const fetchAnnounces = async () => {
      setLoadingAnnounces(true);
      try {
        const params: Record<string, string | number> = { limit: 9 };
        if (selectedCompany.biz_code) {
          params.biz_code = selectedCompany.biz_code;
        }
        const res = await api.get('/announces', { params });
        setAnnounces(res.data);
      } catch {
        setAnnounces([]);
      } finally {
        setLoadingAnnounces(false);
      }
    };

    const fetchSchedules = async () => {
      setLoadingSchedules(true);
      try {
        const res = await api.get('/schedules', {
          params: { company_id: selectedCompany.company_id },
        });
        setSchedules(res.data);
      } catch {
        setSchedules([]);
      } finally {
        setLoadingSchedules(false);
      }
    };

    fetchAnnounces();
    fetchSchedules();
  }, [selectedCompany?.company_id, selectedCompany?.biz_code]);

  if (!selectedCompany) {
    return (
      <Card className="border border-blue-gray-100 shadow-sm">
        <CardBody className="py-10 text-center">
          <div className="mx-auto mb-4 inline-flex rounded-2xl bg-gradient-to-br from-blue-50 to-cyan-50 p-4 ring-1 ring-blue-100">
            <BuildingOffice2Icon className="h-8 w-8 text-blue-600" />
          </div>
          <Typography variant="h5" color="blue-gray" className="mb-2 !text-gray-900">
            기업을 먼저 선택하세요
          </Typography>
          <Typography variant="small" color="gray" className="mx-auto max-w-xl !text-gray-700">
            기업을 클릭하면 해당 기업 기준의 대시보드(공고, 일정, 뉴스)를 볼 수 있습니다.
          </Typography>
        </CardBody>
      </Card>
    );
  }

  return (
    <div>

      <div className="grid gap-4 md:grid-cols-3">
        {/* 최근 공고 */}
        <Card className="hover:shadow-lg transition-shadow">
          <CardBody className="h-[288px] overflow-hidden flex flex-col">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <div className="inline-flex p-2 rounded-full bg-blue-50">
                  <MegaphoneIcon className="h-5 w-5 text-blue-500" />
                </div>
                <Typography variant="h6" color="blue-gray" className="!text-gray-900">
                  최근 공고
                </Typography>
              </div>
              {announces.length > ITEMS_PER_PAGE && (
                <div className="flex items-center gap-1">
                  <button
                    aria-label="이전 페이지"
                    onClick={() => {
                      setCurrentPage((prev) => (prev - 1 + totalPages) % totalPages);
                      resetTimer();
                    }}
                    className="p-1 rounded hover:bg-gray-100 text-gray-500 hover:text-gray-700"
                  >
                    <ChevronLeftIcon className="h-4 w-4" />
                  </button>
                  <Typography variant="small" color="gray" className="text-xs !text-gray-500 min-w-[28px] text-center">
                    {currentPage + 1}/{totalPages}
                  </Typography>
                  <button
                    aria-label="다음 페이지"
                    onClick={() => {
                      setCurrentPage((prev) => (prev + 1) % totalPages);
                      resetTimer();
                    }}
                    className="p-1 rounded hover:bg-gray-100 text-gray-500 hover:text-gray-700"
                  >
                    <ChevronRightIcon className="h-4 w-4" />
                  </button>
                </div>
              )}
            </div>
            {announces.length > 0 ? (
              <ul className="space-y-2">
                {pagedAnnounces.map((ann) => (
                  <li key={ann.announce_id} className="border-b border-gray-100 pb-2 last:border-0">
                    <a
                      href={safeUrl(ann.source_url)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm font-medium text-blue-600 hover:underline line-clamp-1"
                    >
                      {ann.ann_name}
                    </a>
                    <div className="flex justify-between mt-0.5">
                      <Typography variant="small" color="gray" className="text-xs !text-gray-500">
                        {ann.organization || '-'}
                      </Typography>
                      <Typography variant="small" color="gray" className="text-xs !text-gray-500">
                        {ann.apply_end ? `~${formatDate(ann.apply_end)}` : '-'}
                      </Typography>
                    </div>
                  </li>
                ))}
              </ul>
            ) : !loadingAnnounces ? (
              <Typography variant="small" color="gray" className="italic">
                관련 공고가 없습니다.
              </Typography>
            ) : null}
          </CardBody>
        </Card>

        {/* 다가오는 일정 */}
        <Card className="hover:shadow-lg transition-shadow">
          <CardBody className="h-[288px] overflow-hidden flex flex-col">
            <div className="flex items-center gap-2 mb-3">
              <div className="inline-flex p-2 rounded-full bg-green-50">
                <CalendarDaysIcon className="h-5 w-5 text-green-500" />
              </div>
              <Typography variant="h6" color="blue-gray" className="!text-gray-900">
                다가오는 일정
              </Typography>
            </div>
            {schedules.length > 0 ? (
              <ul className="space-y-2">
                {schedules.slice(0, 3).map((sch) => (
                  <li key={sch.schedule_id} className="border-b border-gray-100 pb-2 last:border-0">
                    <Typography variant="small" color="blue-gray" className="font-medium text-sm !text-gray-900 line-clamp-1">
                      {sch.schedule_name}
                    </Typography>
                    <Typography variant="small" color="gray" className="text-xs !text-gray-500">
                      {formatDate(sch.start_date)} ~ {formatDate(sch.end_date)}
                    </Typography>
                  </li>
                ))}
              </ul>
            ) : !loadingSchedules ? (
              <Typography variant="small" color="gray" className="italic">
                등록된 일정이 없습니다.
              </Typography>
            ) : null}
          </CardBody>
        </Card>

        {/* 관련 뉴스 (Coming Soon) */}
        <Card className="hover:shadow-lg transition-shadow">
          <CardBody className="h-[288px] overflow-hidden flex flex-col">
            <div className="flex items-center gap-2 mb-3">
              <div className="inline-flex p-2 rounded-full bg-purple-50">
                <NewspaperIcon className="h-5 w-5 text-purple-500" />
              </div>
              <Typography variant="h6" color="blue-gray" className="!text-gray-900">
                관련 뉴스
              </Typography>
            </div>
            <Typography variant="small" color="gray" className="italic">
              준비 중...
            </Typography>
          </CardBody>
        </Card>
      </div>
    </div>
  );
};
