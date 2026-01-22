import React, { useState, useEffect } from 'react';
import {
  Card,
  CardBody,
  CardHeader,
  Typography,
  Input,
  Button,
  Dialog,
  DialogHeader,
  DialogBody,
  DialogFooter,
  Textarea,
  IconButton,
  Alert,
  Select,
  Option,
} from '@material-tailwind/react';
import { PlusIcon, PencilIcon, TrashIcon } from '@heroicons/react/24/outline';
import api from '../lib/api';
import type { Schedule, Company } from '../types';

const SchedulePage: React.FC = () => {
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingSchedule, setEditingSchedule] = useState<Schedule | null>(null);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const [formData, setFormData] = useState({
    company_id: '',
    schedule_name: '',
    start_date: '',
    end_date: '',
    memo: '',
  });

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

  const openCreateDialog = () => {
    setEditingSchedule(null);
    setFormData({
      company_id: companies[0]?.company_id?.toString() || '',
      schedule_name: '',
      start_date: '',
      end_date: '',
      memo: '',
    });
    setIsDialogOpen(true);
  };

  const openEditDialog = (schedule: Schedule) => {
    setEditingSchedule(schedule);
    setFormData({
      company_id: schedule.company_id.toString(),
      schedule_name: schedule.schedule_name,
      start_date: schedule.start_date.split('T')[0],
      end_date: schedule.end_date.split('T')[0],
      memo: schedule.memo || '',
    });
    setIsDialogOpen(true);
  };

  const handleSave = async () => {
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
    } catch (err: any) {
      setMessage({
        type: 'error',
        text: err.response?.data?.detail || '저장에 실패했습니다.',
      });
    }
  };

  const handleDelete = async (scheduleId: number) => {
    if (!window.confirm('정말 삭제하시겠습니까?')) return;

    try {
      await api.delete(`/schedules/${scheduleId}`);
      setMessage({ type: 'success', text: '일정이 삭제되었습니다.' });
      fetchData();
    } catch (err: any) {
      setMessage({
        type: 'error',
        text: err.response?.data?.detail || '삭제에 실패했습니다.',
      });
    }
  };

  const getCompanyName = (companyId: number) => {
    return companies.find((c) => c.company_id === companyId)?.com_name || '-';
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('ko-KR', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <Typography variant="h4" color="blue-gray">
          일정 관리
        </Typography>
        <Button
          className="flex items-center gap-2"
          onClick={openCreateDialog}
          disabled={companies.length === 0}
        >
          <PlusIcon className="h-4 w-4" />
          일정 추가
        </Button>
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
      ) : schedules.length === 0 ? (
        <Card>
          <CardBody className="text-center py-10">
            <Typography color="gray">등록된 일정이 없습니다.</Typography>
            {companies.length > 0 && (
              <Button className="mt-4" onClick={openCreateDialog}>
                첫 일정 등록하기
              </Button>
            )}
          </CardBody>
        </Card>
      ) : (
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
                    <IconButton
                      variant="text"
                      size="sm"
                      onClick={() => openEditDialog(schedule)}
                    >
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
                    <span className="text-gray-500">시작:</span>{' '}
                    {formatDate(schedule.start_date)}
                  </div>
                  <div>
                    <span className="text-gray-500">종료:</span>{' '}
                    {formatDate(schedule.end_date)}
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

      {/* 등록/수정 다이얼로그 */}
      <Dialog open={isDialogOpen} handler={() => setIsDialogOpen(false)} size="md">
        <DialogHeader>
          {editingSchedule ? '일정 수정' : '일정 등록'}
        </DialogHeader>
        <DialogBody className="space-y-4">
          <div>
            <Typography variant="small" color="gray" className="mb-1">
              기업 *
            </Typography>
            <Select
              value={formData.company_id}
              onChange={(val) => setFormData({ ...formData, company_id: val || '' })}
              className="!border-gray-300"
              labelProps={{ className: 'hidden' }}
            >
              {companies.map((company) => (
                <Option key={company.company_id} value={company.company_id.toString()}>
                  {company.com_name}
                </Option>
              ))}
            </Select>
          </div>
          <div>
            <Typography variant="small" color="gray" className="mb-1">
              일정명 *
            </Typography>
            <Input
              value={formData.schedule_name}
              onChange={(e) => setFormData({ ...formData, schedule_name: e.target.value })}
              className="!border-gray-300"
              labelProps={{ className: 'hidden' }}
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Typography variant="small" color="gray" className="mb-1">
                시작일 *
              </Typography>
              <Input
                type="date"
                value={formData.start_date}
                onChange={(e) => setFormData({ ...formData, start_date: e.target.value })}
                className="!border-gray-300"
                labelProps={{ className: 'hidden' }}
              />
            </div>
            <div>
              <Typography variant="small" color="gray" className="mb-1">
                종료일 *
              </Typography>
              <Input
                type="date"
                value={formData.end_date}
                onChange={(e) => setFormData({ ...formData, end_date: e.target.value })}
                className="!border-gray-300"
                labelProps={{ className: 'hidden' }}
              />
            </div>
          </div>
          <div>
            <Typography variant="small" color="gray" className="mb-1">
              메모
            </Typography>
            <Textarea
              value={formData.memo}
              onChange={(e) => setFormData({ ...formData, memo: e.target.value })}
              className="!border-gray-300"
              labelProps={{ className: 'hidden' }}
            />
          </div>
        </DialogBody>
        <DialogFooter>
          <Button variant="text" onClick={() => setIsDialogOpen(false)}>
            취소
          </Button>
          <Button
            onClick={handleSave}
            disabled={
              !formData.company_id ||
              !formData.schedule_name.trim() ||
              !formData.start_date ||
              !formData.end_date
            }
          >
            저장
          </Button>
        </DialogFooter>
      </Dialog>
    </div>
  );
};

export default SchedulePage;
