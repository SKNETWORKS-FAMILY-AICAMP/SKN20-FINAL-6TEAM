import React, { useState } from 'react';
import {
  Card,
  CardBody,
  CardHeader,
  Typography,
  Input,
  Button,
  Select,
  Option,
  Chip,
  Alert,
} from '@material-tailwind/react';
import { INDUSTRY_CODES } from '../../lib/constants';
import api from '../../lib/api';
import { useAuthStore } from '../../stores/authStore';

interface PreStartupFormData {
  biz_code: string;
  open_date: string;
  addr: string;
}

export const PreStartupCompanyForm: React.FC = () => {
  const { updateUser } = useAuthStore();
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [formData, setFormData] = useState<PreStartupFormData>({
    biz_code: '',
    open_date: '',
    addr: '',
  });

  const handleSave = async () => {
    setIsSaving(true);
    setMessage(null);

    try {
      await api.post('/companies', {
        com_name: '(예비) 창업 준비',
        biz_num: '',
        biz_code: formData.biz_code,
        open_date: formData.open_date ? new Date(formData.open_date).toISOString() : null,
        addr: formData.addr,
      });

      // Update user type to 사업자 (U003) after successful company registration
      try {
        await api.put('/users/me/type', { type_code: 'U003' });
        updateUser({ type_code: 'U003' });
      } catch {
        // Non-critical: company was saved, type update failure is acceptable
      }

      setMessage({ type: 'success', text: '정보가 저장되었습니다.' });
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      setMessage({
        type: 'error',
        text: error.response?.data?.detail || '저장에 실패했습니다.',
      });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Card className="max-w-2xl">
      <CardHeader floated={false} shadow={false} className="rounded-none">
        <div className="flex items-center gap-3">
          <Typography variant="h5" color="blue-gray">
            예비 창업 정보
          </Typography>
          <Chip value="준비 중" color="amber" size="sm" />
        </div>
      </CardHeader>
      <CardBody className="space-y-4">
        {message && (
          <Alert
            color={message.type === 'success' ? 'green' : 'red'}
            onClose={() => setMessage(null)}
          >
            {message.text}
          </Alert>
        )}

        {/* Business Status */}
        <div>
          <Typography variant="small" color="gray" className="mb-1">
            기업 상태
          </Typography>
          <Input
            value="준비 중"
            disabled
            className="!border-gray-300"
            labelProps={{ className: 'hidden' }}
          />
        </div>

        {/* Business Number */}
        <div>
          <Typography variant="small" color="gray" className="mb-1">
            사업자등록번호
          </Typography>
          <Input
            value="없음"
            disabled
            className="!border-gray-300"
            labelProps={{ className: 'hidden' }}
          />
        </div>

        {/* Desired Industry */}
        <div>
          <Typography variant="small" color="gray" className="mb-1">
            희망 업종
          </Typography>
          <Select
            value={formData.biz_code}
            onChange={(val) => setFormData({ ...formData, biz_code: val || '' })}
            className="!border-gray-300"
            labelProps={{ className: 'hidden' }}
          >
            {Object.entries(INDUSTRY_CODES).map(([code, name]) => (
              <Option key={code} value={code}>
                {name}
              </Option>
            ))}
          </Select>
        </div>

        {/* Expected Start Date */}
        <div>
          <Typography variant="small" color="gray" className="mb-1">
            사업 시작 예정일
          </Typography>
          <Input
            type="date"
            value={formData.open_date}
            onChange={(e) => setFormData({ ...formData, open_date: e.target.value })}
            className="!border-gray-300"
            labelProps={{ className: 'hidden' }}
          />
        </div>

        {/* Region */}
        <div>
          <Typography variant="small" color="gray" className="mb-1">
            지역
          </Typography>
          <Input
            value={formData.addr}
            onChange={(e) => setFormData({ ...formData, addr: e.target.value })}
            placeholder="예: 서울특별시 강남구"
            className="!border-gray-300"
            labelProps={{ className: 'hidden' }}
          />
        </div>

        <Button onClick={handleSave} disabled={isSaving} className="mt-4">
          {isSaving ? '저장 중...' : '저장'}
        </Button>
      </CardBody>
    </Card>
  );
};
