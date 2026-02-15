import React, { useState, useEffect } from 'react';
import {
  Card,
  CardBody,
  CardHeader,
  Typography,
  Button,
  IconButton,
  Alert,
  ButtonGroup,
} from '@material-tailwind/react';
import {
  PlusIcon,
  PencilIcon,
  TrashIcon,
  CalendarIcon,
  ListBulletIcon,
} from '@heroicons/react/24/outline';
import api from '../lib/api';
import { extractErrorMessage } from '../lib/errorHandler';
import { formatDateLong } from '../lib/dateUtils';
import { CalendarView } from '../components/schedule/CalendarView';
import { ScheduleDetailDialog } from '../components/schedule/ScheduleDetailDialog';
import type { ScheduleFormData } from '../components/schedule/ScheduleDetailDialog';
import { useNotifications } from '../hooks/useNotifications';
import type { Schedule, Company } from '../types';

type ViewMode = 'calendar' | 'list';

const SchedulePage: React.FC = () => {
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingSchedule, setEditingSchedule] = useState<Schedule | null>(null);
  const [defaultDate, setDefaultDate] = useState<string>('');
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>('calendar');

  // Generate notifications for upcoming deadlines
  useNotifications(schedules);

  const fetchData = async () => {
    try {
      const [schedulesRes, companiesRes] = await Promise.all([
        api.get('/schedules'),
        api.get('/companies'),
      ]);
      setSchedules(schedulesRes.data);
      setCompanies(companiesRes.data);
    } catch (err) {
      console.error('Failed to fetch data:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

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
        company_id: parseInt(formData.company_id),
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
      fetchData();
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
      fetchData();
    } catch (err: unknown) {
      setMessage({
        type: 'error',
        text: extractErrorMessage(err, '삭제에 실패했습니다.'),
      });
    }
  };

  const handleDateClick = (dateStr: string) => {
    if (companies.length === 0) return;
    openCreateDialog(dateStr);
  };

  const handleEventClick = (scheduleId: number) => {
    const schedule = schedules.find((s) => s.schedule_id === scheduleId);
    if (schedule) {
      openEditDialog(schedule);
    }
  };

  const getCompanyName = (companyId: number) => {
    return companies.find((c) => c.company_id === companyId)?.com_name || '-';
  };

  const formatDate = (dateStr: string) => formatDateLong(dateStr);

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <Typography variant="h4" color="blue-gray">
          일정 관리
        </Typography>
        <div className="flex items-center gap-3">
          {/* View mode toggle */}
          <ButtonGroup variant="outlined" size="sm">
            <Button
              className={`flex items-center gap-1 ${viewMode === 'calendar' ? 'bg-blue-50' : ''}`}
              onClick={() => setViewMode('calendar')}
            >
              <CalendarIcon className="h-4 w-4" />
              캘린더
            </Button>
            <Button
              className={`flex items-center gap-1 ${viewMode === 'list' ? 'bg-blue-50' : ''}`}
              onClick={() => setViewMode('list')}
            >
              <ListBulletIcon className="h-4 w-4" />
              리스트
            </Button>
          </ButtonGroup>

          <Button
            className="flex items-center gap-2"
            onClick={() => openCreateDialog()}
            disabled={companies.length === 0}
          >
            <PlusIcon className="h-4 w-4" />
            일정 추가
          </Button>
        </div>
      </div>

      {message && (
        <Alert
          color={message.type === 'success' ? 'green' : 'red'}
          className="mb-4"
          onClose={() => setMessage(null)}
        >
          {message.text}
        </Alert>
      )}

      {companies.length === 0 && !isLoading && (
        <Alert color="amber" className="mb-4">
          먼저 기업 정보를 등록해주세요. 일정은 기업에 연결됩니다.
        </Alert>
      )}

      {isLoading ? (
        <div className="text-center py-10">
          <Typography color="gray">로딩 중...</Typography>
        </div>
      ) : viewMode === 'calendar' ? (
        /* Calendar View */
        <CalendarView
          schedules={schedules}
          onDateClick={handleDateClick}
          onEventClick={handleEventClick}
        />
      ) : schedules.length === 0 ? (
        /* Empty list */
        <Card>
          <CardBody className="text-center py-10">
            <Typography color="gray">등록된 일정이 없습니다.</Typography>
            {companies.length > 0 && (
              <Button className="mt-4" onClick={() => openCreateDialog()}>
                첫 일정 등록하기
              </Button>
            )}
          </CardBody>
        </Card>
      ) : (
        /* List View */
        <div className="space-y-4">
          {schedules.map((schedule) => (
            <Card key={schedule.schedule_id}>
              <CardHeader floated={false} shadow={false} className="rounded-none">
                <div className="flex items-center justify-between">
                  <div>
                    <Typography variant="h6" color="blue-gray">
                      {schedule.schedule_name}
                    </Typography>
                    <Typography variant="small" color="gray">
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
                      onClick={() => handleDelete(schedule.schedule_id)}
                    >
                      <TrashIcon className="h-4 w-4" />
                    </IconButton>
                  </div>
                </div>
              </CardHeader>
              <CardBody className="pt-0">
                <div className="flex gap-6 text-sm">
                  <div>
                    <span className="text-gray-500">시작:</span> {formatDate(schedule.start_date)}
                  </div>
                  <div>
                    <span className="text-gray-500">종료:</span> {formatDate(schedule.end_date)}
                  </div>
                </div>
                {schedule.memo && (
                  <Typography variant="small" color="gray" className="mt-2">
                    {schedule.memo}
                  </Typography>
                )}
              </CardBody>
            </Card>
          ))}
        </div>
      )}

      {/* Schedule Dialog */}
      <ScheduleDetailDialog
        open={isDialogOpen}
        onClose={() => setIsDialogOpen(false)}
        onSave={handleSave}
        onDelete={handleDelete}
        schedule={editingSchedule}
        companies={companies}
        defaultDate={defaultDate}
      />
    </div>
  );
};

export default SchedulePage;
