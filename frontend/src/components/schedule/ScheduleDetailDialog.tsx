import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogHeader,
  DialogBody,
  DialogFooter,
  Typography,
  Input,
  Button,
  Textarea,
  Select,
  Option,
} from '@material-tailwind/react';
import type { Schedule, Company } from '../../types';

interface ScheduleDetailDialogProps {
  open: boolean;
  onClose: () => void;
  onSave: (data: ScheduleFormData) => void;
  onDelete?: (scheduleId: number) => void;
  schedule: Schedule | null;
  companies: Company[];
  defaultDate?: string;
  defaultCompanyId?: number | null;
}

export interface ScheduleFormData {
  company_id: string;
  schedule_name: string;
  start_date: string;
  end_date: string;
  memo: string;
}

export const ScheduleDetailDialog: React.FC<ScheduleDetailDialogProps> = ({
  open,
  onClose,
  onSave,
  onDelete,
  schedule,
  companies,
  defaultDate,
  defaultCompanyId,
}) => {
  const [formData, setFormData] = useState<ScheduleFormData>({
    company_id: '',
    schedule_name: '',
    start_date: '',
    end_date: '',
    memo: '',
  });

  useEffect(() => {
    if (schedule) {
      setFormData({
        company_id: schedule.company_id.toString(),
        schedule_name: schedule.schedule_name,
        start_date: schedule.start_date.split('T')[0],
        end_date: schedule.end_date.split('T')[0],
        memo: schedule.memo || '',
      });
    } else {
      const fallbackCompanyId =
        defaultCompanyId ?? companies[0]?.company_id ?? null;
      setFormData({
        company_id: fallbackCompanyId ? fallbackCompanyId.toString() : '',
        schedule_name: '',
        start_date: defaultDate || '',
        end_date: defaultDate || '',
        memo: '',
      });
    }
  }, [schedule, companies, defaultDate, defaultCompanyId]);

  const isValid =
    formData.company_id &&
    formData.schedule_name.trim() &&
    formData.start_date &&
    formData.end_date;

  return (
    <Dialog open={open} handler={onClose} size="md">
      <DialogHeader>
        {schedule ? '일정 수정' : '일정 등록'}
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
      <DialogFooter className="flex justify-between">
        <div>
          {schedule && onDelete && (
            <Button
              variant="text"
              color="red"
              onClick={() => onDelete(schedule.schedule_id)}
            >
              삭제
            </Button>
          )}
        </div>
        <div className="flex gap-2">
          <Button variant="text" onClick={onClose}>
            취소
          </Button>
          <Button onClick={() => onSave(formData)} disabled={!isValid}>
            저장
          </Button>
        </div>
      </DialogFooter>
    </Dialog>
  );
};
