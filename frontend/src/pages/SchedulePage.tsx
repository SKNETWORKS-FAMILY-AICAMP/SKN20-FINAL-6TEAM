import React, { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Button,
  ButtonGroup,
  Card,
  CardBody,
  CardHeader,
  Dialog,
  DialogBody,
  DialogFooter,
  DialogHeader,
  IconButton,
  Textarea,
  Typography,
} from '@material-tailwind/react';
import {
  ArrowTopRightOnSquareIcon,
  CalendarIcon,
  ListBulletIcon,
  MinusIcon,
  PencilIcon,
  PlusIcon,
  TrashIcon,
} from '@heroicons/react/24/outline';
import api from '../lib/api';
import { extractErrorMessage } from '../lib/errorHandler';
import { formatDateLong } from '../lib/dateUtils';
import { CalendarView } from '../components/schedule/CalendarView';
import { CalendarErrorBoundary } from '../components/schedule/CalendarErrorBoundary';
import { ScheduleDetailDialog } from '../components/schedule/ScheduleDetailDialog';
import type { ScheduleFormData } from '../components/schedule/ScheduleDetailDialog';
import { useNotifications } from '../hooks/useNotifications';
import { PageHeader } from '../components/common/PageHeader';
import type { Announce, Company, Schedule } from '../types';

type ViewMode = 'calendar' | 'list';

const RELATED_ANNOUNCE_LIMIT = 20;

const isValidDateString = (value: unknown): value is string =>
  typeof value === 'string' && !Number.isNaN(new Date(value).getTime());

const normalizeSchedules = (value: unknown): Schedule[] => {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .filter((item): item is Partial<Schedule> => typeof item === 'object' && item !== null)
    .filter(
      (item): item is Schedule =>
        typeof item.schedule_id === 'number' &&
        typeof item.company_id === 'number' &&
        typeof item.schedule_name === 'string' &&
        isValidDateString(item.start_date) &&
        isValidDateString(item.end_date)
    )
    .map((item) => ({
      schedule_id: item.schedule_id,
      company_id: item.company_id,
      announce_id: item.announce_id,
      schedule_name: item.schedule_name,
      start_date: item.start_date,
      end_date: item.end_date,
      memo: item.memo ?? '',
      create_date: item.create_date,
    }));
};

const normalizeCompanies = (value: unknown): Company[] => {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .filter((item): item is Partial<Company> => typeof item === 'object' && item !== null)
    .filter(
      (item): item is Company =>
        typeof item.company_id === 'number' && typeof item.com_name === 'string'
    )
    .map((item) => ({
      company_id: item.company_id,
      user_id: typeof item.user_id === 'number' ? item.user_id : 0,
      com_name: item.com_name,
      biz_num: typeof item.biz_num === 'string' ? item.biz_num : '',
      addr: typeof item.addr === 'string' ? item.addr : '',
      open_date: item.open_date,
      biz_code: item.biz_code,
      file_path: typeof item.file_path === 'string' ? item.file_path : '',
      main_yn: typeof item.main_yn === 'boolean' ? item.main_yn : false,
      create_date: item.create_date,
    }));
};

const normalizeAnnounces = (value: unknown): Announce[] => {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .filter((item): item is Partial<Announce> => typeof item === 'object' && item !== null)
    .filter(
      (item): item is Announce =>
        typeof item.announce_id === 'number' &&
        typeof item.ann_name === 'string' &&
        typeof item.source_type === 'string' &&
        typeof item.region === 'string' &&
        typeof item.organization === 'string' &&
        typeof item.source_url === 'string'
    )
    .map((item) => ({
      announce_id: item.announce_id,
      ann_name: item.ann_name,
      source_type: item.source_type,
      apply_start: item.apply_start,
      apply_end: item.apply_end,
      region: item.region,
      organization: item.organization,
      source_url: item.source_url,
      biz_code: item.biz_code,
      create_date: item.create_date,
    }));
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

const toDatePart = (value: string | undefined): string | null => {
  if (!value) {
    return null;
  }

  const datePart = value.includes('T') ? value.split('T')[0] : value;
  const parsed = new Date(datePart);
  if (Number.isNaN(parsed.getTime())) {
    return null;
  }

  return datePart;
};

const formatPeriod = (start: string | undefined, end: string | undefined): string => {
  const startPart = toDatePart(start);
  const endPart = toDatePart(end);

  if (startPart && endPart) {
    return `${startPart} ~ ${endPart}`;
  }

  return startPart ?? endPart ?? '일정 미정';
};

const buildDefaultAnnounceMemo = (announce: Announce): string =>
  `자동 등록 공고 일정\n기관: ${announce.organization || '-'}\nURL: ${announce.source_url || '-'}`;

const buildAnnounceSchedulePayload = (announce: Announce, companyId: number, memo: string) => {
  const today = new Date().toISOString().split('T')[0];
  const startDatePart = toDatePart(announce.apply_start) ?? toDatePart(announce.apply_end) ?? today;
  const endDatePart = toDatePart(announce.apply_end) ?? toDatePart(announce.apply_start) ?? startDatePart;

  const startDate = new Date(`${startDatePart}T09:00:00`);
  const rawEndDate = new Date(`${endDatePart}T18:00:00`);
  const endDate = rawEndDate.getTime() < startDate.getTime() ? startDate : rawEndDate;

  return {
    company_id: companyId,
    announce_id: announce.announce_id,
    schedule_name: announce.ann_name,
    start_date: startDate.toISOString(),
    end_date: endDate.toISOString(),
    memo,
  };
};

const SchedulePage: React.FC = () => {
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [relatedAnnounces, setRelatedAnnounces] = useState<Announce[]>([]);
  const [selectedCompanyId, setSelectedCompanyId] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingRelatedAnnounces, setIsLoadingRelatedAnnounces] = useState(false);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [isAnnounceDialogOpen, setIsAnnounceDialogOpen] = useState(false);
  const [editingSchedule, setEditingSchedule] = useState<Schedule | null>(null);
  const [pendingAnnounce, setPendingAnnounce] = useState<Announce | null>(null);
  const [announceAdditionalMemo, setAnnounceAdditionalMemo] = useState('');
  const [defaultDate, setDefaultDate] = useState<string>('');
  const [processingAnnounceId, setProcessingAnnounceId] = useState<number | null>(null);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>('calendar');

  useNotifications(schedules);

  const selectedCompany = useMemo(
    () => companies.find((company) => company.company_id === selectedCompanyId) ?? null,
    [companies, selectedCompanyId]
  );

  const filteredSchedules = useMemo(() => {
    if (!selectedCompanyId) {
      return schedules;
    }

    return schedules.filter((schedule) => schedule.company_id === selectedCompanyId);
  }, [schedules, selectedCompanyId]);

  const fetchData = async () => {
    try {
      const [schedulesResult, companiesResult] = await Promise.allSettled([
        api.get('/schedules'),
        api.get('/companies'),
      ]);

      if (schedulesResult.status === 'fulfilled') {
        setSchedules(normalizeSchedules(schedulesResult.value.data));
      } else {
        console.error('Failed to fetch schedules:', schedulesResult.reason);
      }

      if (companiesResult.status === 'fulfilled') {
        setCompanies(normalizeCompanies(companiesResult.value.data));
      } else {
        console.error('Failed to fetch companies:', companiesResult.reason);
      }
    } catch (err) {
      console.error('Failed to fetch data:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void fetchData();
  }, []);

  useEffect(() => {
    if (!message) {
      return;
    }

    const timeoutId = window.setTimeout(() => {
      setMessage(null);
    }, 5000);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [message]);

  useEffect(() => {
    if (companies.length === 0) {
      setSelectedCompanyId(null);
      return;
    }

    setSelectedCompanyId((current) => {
      if (current && companies.some((company) => company.company_id === current)) {
        return current;
      }

      const mainCompany = companies.find((company) => company.main_yn);
      return mainCompany?.company_id ?? companies[0].company_id;
    });
  }, [companies]);

  useEffect(() => {
    if (!selectedCompany) {
      setRelatedAnnounces([]);
      return;
    }

    if (!selectedCompany.biz_code) {
      setRelatedAnnounces([]);
      return;
    }

    let mounted = true;

    const fetchRelatedAnnounces = async () => {
      setIsLoadingRelatedAnnounces(true);
      try {
        const response = await api.get('/announces', {
          params: {
            biz_code: selectedCompany.biz_code,
            limit: RELATED_ANNOUNCE_LIMIT,
          },
        });

        if (!mounted) {
          return;
        }

        setRelatedAnnounces(normalizeAnnounces(response.data));
      } catch (err) {
        if (!mounted) {
          return;
        }

        console.error('Failed to fetch related announces:', err);
        setRelatedAnnounces([]);
      } finally {
        if (mounted) {
          setIsLoadingRelatedAnnounces(false);
        }
      }
    };

    void fetchRelatedAnnounces();

    return () => {
      mounted = false;
    };
  }, [selectedCompany]);

  const openCreateDialog = (dateStr?: string) => {
    setEditingSchedule(null);
    setDefaultDate(dateStr || '');
    setIsDialogOpen(true);
  };

  const openEditDialog = (schedule: Schedule) => {
    setEditingSchedule(schedule);
    setDefaultDate('');
    setIsDialogOpen(true);
  };

  const handleSave = async (formData: ScheduleFormData) => {
    try {
      const data = {
        company_id: parseInt(formData.company_id, 10),
        schedule_name: formData.schedule_name,
        start_date: new Date(formData.start_date).toISOString(),
        end_date: new Date(formData.end_date).toISOString(),
        memo: formData.memo,
      };

      if (editingSchedule) {
        await api.put(`/schedules/${editingSchedule.schedule_id}`, data);
        setMessage({ type: 'success', text: '일정이 수정되었습니다.' });
      } else {
        await api.post('/schedules', data);
        setMessage({ type: 'success', text: '일정이 등록되었습니다.' });
      }

      setIsDialogOpen(false);
      await fetchData();
    } catch (err: unknown) {
      setMessage({
        type: 'error',
        text: extractErrorMessage(err, '저장에 실패했습니다.'),
      });
    }
  };

  const handleDelete = async (scheduleId: number) => {
    if (!window.confirm('정말 삭제하시겠습니까?')) return;

    try {
      await api.delete(`/schedules/${scheduleId}`);
      setMessage({ type: 'success', text: '일정이 삭제되었습니다.' });
      setIsDialogOpen(false);
      await fetchData();
    } catch (err: unknown) {
      setMessage({
        type: 'error',
        text: extractErrorMessage(err, '삭제에 실패했습니다.'),
      });
    }
  };

  const handleDateClick = (dateStr: string) => {
    if (!selectedCompanyId) return;
    openCreateDialog(dateStr);
  };

  const handleEventClick = (scheduleId: number) => {
    const schedule = schedules.find((item) => item.schedule_id === scheduleId);
    if (schedule) {
      openEditDialog(schedule);
    }
  };

  const getCompanyName = (companyId: number) => {
    return companies.find((company) => company.company_id === companyId)?.com_name || '-';
  };

  const handleCalendarError = () => {
    setViewMode('list');
    setMessage({
      type: 'error',
      text: '캘린더 렌더링 중 오류가 발생해 리스트 보기로 전환되었습니다.',
    });
  };

  const isAnnounceLinked = (announceId: number): boolean => {
    if (!selectedCompanyId) {
      return false;
    }

    return schedules.some(
      (schedule) => schedule.company_id === selectedCompanyId && schedule.announce_id === announceId
    );
  };

  const getLinkedSchedule = (announceId: number): Schedule | undefined => {
    if (!selectedCompanyId) {
      return undefined;
    }

    return schedules.find(
      (schedule) => schedule.company_id === selectedCompanyId && schedule.announce_id === announceId
    );
  };

  const handleCreateScheduleFromAnnounce = async (announce: Announce) => {
    if (!selectedCompanyId) {
      return;
    }

    if (isAnnounceLinked(announce.announce_id)) {
      setMessage({
        type: 'error',
        text: '해당 공고는 이미 일정에 등록되어 있습니다.',
      });
      return;
    }

    setPendingAnnounce(announce);
    setAnnounceAdditionalMemo('');
    setIsAnnounceDialogOpen(true);
  };

  const closeAnnounceDialog = () => {
    setIsAnnounceDialogOpen(false);
    setPendingAnnounce(null);
    setAnnounceAdditionalMemo('');
  };

  const handleConfirmCreateScheduleFromAnnounce = async () => {
    if (!selectedCompanyId || !pendingAnnounce) {
      return;
    }

    const announce = pendingAnnounce;
    const baseMemo = buildDefaultAnnounceMemo(announce);
    const finalMemo = announceAdditionalMemo.trim()
      ? `${baseMemo}\n\n추가 메모\n${announceAdditionalMemo.trim()}`
      : baseMemo;

    setProcessingAnnounceId(announce.announce_id);
    try {
      const payload = buildAnnounceSchedulePayload(announce, selectedCompanyId, finalMemo);
      await api.post('/schedules', payload);
      setMessage({
        type: 'success',
        text: '공고 일정이 캘린더에 자동 등록되었습니다.',
      });
      await fetchData();
      closeAnnounceDialog();
    } catch (err: unknown) {
      setMessage({
        type: 'error',
        text: extractErrorMessage(err, '공고 일정 등록에 실패했습니다.'),
      });
    } finally {
      setProcessingAnnounceId(null);
    }
  };

  const handleRemoveScheduleFromAnnounce = async (announceId: number) => {
    const linkedSchedule = getLinkedSchedule(announceId);
    if (!linkedSchedule) {
      return;
    }

    setProcessingAnnounceId(announceId);
    try {
      await api.delete(`/schedules/${linkedSchedule.schedule_id}`);
      setMessage({
        type: 'success',
        text: '공고 일정이 캘린더에서 제거되었습니다.',
      });
      await fetchData();
    } catch (err: unknown) {
      setMessage({
        type: 'error',
        text: extractErrorMessage(err, '공고 일정 제거에 실패했습니다.'),
      });
    } finally {
      setProcessingAnnounceId(null);
    }
  };

  const relatedAnnouncePanel = (
    <Card className="h-full min-h-[360px] overflow-hidden">
      <CardHeader
        floated={false}
        shadow={false}
        color="transparent"
        className="m-0 rounded-none border-b border-gray-200 px-4 py-3"
      >
        <div className="flex items-center justify-between gap-2">
          <Typography variant="h6" color="blue-gray" className="!text-gray-900">
            관련 공고
          </Typography>
          <Typography variant="small" color="gray" className="!text-gray-600">
            {selectedCompany ? selectedCompany.com_name : '기업 선택 필요'}
          </Typography>
        </div>
      </CardHeader>
      <CardBody className="h-[calc(100%-57px)] overflow-y-auto p-3">
        {!selectedCompany ? (
          <Typography color="gray" className="text-sm">
            기업을 선택하면 관련 공고를 확인할 수 있습니다.
          </Typography>
        ) : !selectedCompany.biz_code ? (
          <Typography color="gray" className="text-sm">
            선택한 기업에 업종 코드가 없어 관련 공고를 조회할 수 없습니다.
          </Typography>
        ) : isLoadingRelatedAnnounces ? (
          <Typography color="gray" className="text-sm">
            공고를 불러오는 중입니다...
          </Typography>
        ) : relatedAnnounces.length === 0 ? (
          <Typography color="gray" className="text-sm">
            조회된 관련 공고가 없습니다.
          </Typography>
        ) : (
          <ul className="space-y-2">
            {relatedAnnounces.map((announce) => {
              const linkedSchedule = getLinkedSchedule(announce.announce_id);
              const alreadyLinked = Boolean(linkedSchedule);
              const isProcessing = processingAnnounceId === announce.announce_id;

              return (
                <li key={announce.announce_id} className="rounded-lg border border-gray-200 p-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <a
                        href={safeUrl(announce.source_url)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="line-clamp-2 text-sm font-semibold text-blue-700 hover:underline"
                      >
                        {announce.ann_name}
                      </a>
                      <Typography variant="small" color="gray" className="mt-1 !text-xs !text-gray-600">
                        {announce.organization || '-'}
                      </Typography>
                      <Typography variant="small" color="gray" className="!text-xs !text-gray-500">
                        {formatPeriod(announce.apply_start, announce.apply_end)}
                      </Typography>
                    </div>

                    <div className="flex shrink-0 items-center gap-1">
                      <a
                        href={safeUrl(announce.source_url)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex h-8 w-8 items-center justify-center rounded-md text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-700"
                        aria-label="공고 원문 보기"
                      >
                        <ArrowTopRightOnSquareIcon className="h-4 w-4" />
                      </a>
                      <IconButton
                        size="sm"
                        variant={alreadyLinked ? 'filled' : 'outlined'}
                        color={alreadyLinked ? 'red' : 'blue'}
                        onClick={() =>
                          alreadyLinked
                            ? void handleRemoveScheduleFromAnnounce(announce.announce_id)
                            : void handleCreateScheduleFromAnnounce(announce)
                        }
                        disabled={isProcessing}
                        title={alreadyLinked ? '일정 제거' : '일정 자동 등록'}
                      >
                        {alreadyLinked ? (
                          <MinusIcon className="h-4 w-4" />
                        ) : (
                          <PlusIcon className="h-4 w-4" />
                        )}
                      </IconButton>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </CardBody>
    </Card>
  );

  const scheduleHeaderControls = (
    <div className="flex flex-wrap items-center gap-2">
      <div className="min-w-[220px]">
        <select
          value={selectedCompanyId?.toString() ?? ''}
          onChange={(event) => {
            const nextValue = event.target.value;
            setSelectedCompanyId(nextValue ? Number(nextValue) : null);
          }}
          disabled={companies.length === 0}
          className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-800 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100 disabled:cursor-not-allowed disabled:bg-gray-100"
        >
          {companies.length === 0 ? (
            <option value="">{'\uAE30\uC5C5 \uC120\uD0DD \uD544\uC694'}</option>
          ) : null}
          {companies.map((company) => (
            <option key={company.company_id} value={company.company_id}>
              {company.com_name}
            </option>
          ))}
        </select>
      </div>

      <ButtonGroup variant="outlined" size="sm">
        <Button
          className={`flex items-center gap-1 ${viewMode === 'calendar' ? 'bg-blue-50' : ''}`}
          onClick={() => setViewMode('calendar')}
        >
          <CalendarIcon className="h-4 w-4" />
          {'\uCE98\uB9B0\uB354'}
        </Button>
        <Button
          className={`flex items-center gap-1 ${viewMode === 'list' ? 'bg-blue-50' : ''}`}
          onClick={() => setViewMode('list')}
        >
          <ListBulletIcon className="h-4 w-4" />
          {'\uB9AC\uC2A4\uD2B8'}
        </Button>
      </ButtonGroup>

      <Button
        size="sm"
        className="flex items-center gap-1"
        onClick={() => openCreateDialog()}
        disabled={companies.length === 0}
      >
        <PlusIcon className="h-4 w-4" />
        {'\uC77C\uC815 \uCD94\uAC00'}
      </Button>
    </div>
  );

  return (
    <div className="flex h-full min-h-0 flex-col">
      <PageHeader
        title={'\uC77C\uC815 \uAD00\uB9AC'}
        contentClassName="flex-wrap"
        rightSlot={scheduleHeaderControls}
      />

      <div className="min-h-0 flex-1 flex flex-col p-3 lg:p-4">
      {message && (
        <Alert
          color={message.type === 'success' ? 'green' : 'red'}
          className="mb-3"
          onClose={() => setMessage(null)}
        >
          {message.text}
        </Alert>
      )}

      {companies.length === 0 && !isLoading && (
        <Alert color="amber" className="mb-3">
          먼저 기업 정보를 등록해주세요. 일정은 기업 단위로 관리됩니다.
        </Alert>
      )}

      {isLoading ? (
        <div className="py-10 text-center">
          <Typography color="gray">로딩 중...</Typography>
        </div>
      ) : viewMode === 'calendar' ? (
        <div className="grid flex-1 min-h-0 gap-3 xl:grid-cols-[minmax(0,1fr)_320px]">
          <CalendarErrorBoundary
            onError={handleCalendarError}
            fallback={(
              <Alert color="red">
                캘린더를 불러오는 중 오류가 발생했습니다. 리스트 보기로 전환해 확인해주세요.
              </Alert>
            )}
          >
            <CalendarView
              schedules={filteredSchedules}
              onDateClick={handleDateClick}
              onEventClick={handleEventClick}
              className="h-full min-h-[360px]"
            />
          </CalendarErrorBoundary>
          {relatedAnnouncePanel}
        </div>
      ) : (
        <div className="grid flex-1 min-h-0 gap-3 xl:grid-cols-[minmax(0,1fr)_320px]">
          <div className="min-h-0 space-y-3 overflow-y-auto">
            {filteredSchedules.length === 0 ? (
              <Card>
                <CardBody className="py-10 text-center">
                  <Typography color="gray">
                    {selectedCompany ? `${selectedCompany.com_name}에 등록된 일정이 없습니다.` : '등록된 일정이 없습니다.'}
                  </Typography>
                  {companies.length > 0 && (
                    <Button className="mt-4" onClick={() => openCreateDialog()}>
                      첫 일정 등록하기
                    </Button>
                  )}
                </CardBody>
              </Card>
            ) : (
              filteredSchedules.map((schedule) => (
                <Card key={schedule.schedule_id}>
                  <CardHeader floated={false} shadow={false} className="rounded-none">
                    <div className="flex items-center justify-between">
                      <div>
                        <Typography variant="h6" color="blue-gray" className="!text-gray-900">
                          {schedule.schedule_name}
                        </Typography>
                        <Typography variant="small" color="gray" className="!text-gray-700">
                          {getCompanyName(schedule.company_id)}
                        </Typography>
                      </div>
                      <div className="flex gap-1">
                        <IconButton variant="text" size="sm" onClick={() => openEditDialog(schedule)}>
                          <PencilIcon className="h-4 w-4" />
                        </IconButton>
                        <IconButton
                          variant="text"
                          size="sm"
                          color="red"
                          onClick={() => void handleDelete(schedule.schedule_id)}
                        >
                          <TrashIcon className="h-4 w-4" />
                        </IconButton>
                      </div>
                    </div>
                  </CardHeader>
                  <CardBody className="pt-0">
                    <div className="flex flex-wrap gap-4 text-sm">
                      <div>
                        <span className="text-gray-600">시작:</span> {formatDateLong(schedule.start_date)}
                      </div>
                      <div>
                        <span className="text-gray-600">종료:</span> {formatDateLong(schedule.end_date)}
                      </div>
                    </div>
                    {schedule.memo && (
                      <Typography variant="small" color="gray" className="mt-2 whitespace-pre-line">
                        {schedule.memo}
                      </Typography>
                    )}
                  </CardBody>
                </Card>
              ))
            )}
          </div>
          {relatedAnnouncePanel}
        </div>
      )}
      </div>

      <Dialog open={isAnnounceDialogOpen} handler={closeAnnounceDialog} size="sm">
        <DialogHeader>공고 일정 자동 등록</DialogHeader>
        <DialogBody className="space-y-3">
          <div>
            <Typography variant="small" color="blue-gray" className="font-semibold !text-gray-900">
              {pendingAnnounce?.ann_name ?? '-'}
            </Typography>
            <Typography variant="small" color="gray" className="mt-1 !text-xs !text-gray-600">
              {pendingAnnounce ? formatPeriod(pendingAnnounce.apply_start, pendingAnnounce.apply_end) : ''}
            </Typography>
          </div>

          <div>
            <Typography variant="small" color="gray" className="mb-1">
              기본 메모 (수정 불가)
            </Typography>
            <Textarea
              value={pendingAnnounce ? buildDefaultAnnounceMemo(pendingAnnounce) : ''}
              readOnly
              disabled
              className="!border-gray-300 !bg-gray-50 !text-gray-600"
              labelProps={{ className: 'hidden' }}
            />
          </div>

          <div>
            <Typography variant="small" color="gray" className="mb-1">
              추가 메모
            </Typography>
            <Textarea
              value={announceAdditionalMemo}
              onChange={(event) => setAnnounceAdditionalMemo(event.target.value)}
              className="!border-gray-300"
              labelProps={{ className: 'hidden' }}
              placeholder="추가로 남길 메모를 입력하세요."
            />
          </div>
        </DialogBody>
        <DialogFooter className="flex gap-2">
          <Button variant="text" onClick={closeAnnounceDialog}>
            취소
          </Button>
          <Button
            onClick={() => void handleConfirmCreateScheduleFromAnnounce()}
            disabled={!pendingAnnounce || processingAnnounceId === pendingAnnounce.announce_id}
          >
            등록
          </Button>
        </DialogFooter>
      </Dialog>

      <ScheduleDetailDialog
        open={isDialogOpen}
        onClose={() => setIsDialogOpen(false)}
        onSave={handleSave}
        onDelete={handleDelete}
        schedule={editingSchedule}
        companies={companies}
        defaultDate={defaultDate}
        defaultCompanyId={selectedCompanyId}
      />
    </div>
  );
};

export default SchedulePage;
