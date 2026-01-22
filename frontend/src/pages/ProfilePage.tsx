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
  Alert,
} from '@material-tailwind/react';
import { useAuthStore } from '../stores/authStore';
import { USER_TYPE_NAMES } from '../types';
import api from '../lib/api';

const ProfilePage: React.FC = () => {
  const { user, updateUser } = useAuthStore();
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const [formData, setFormData] = useState({
    username: user?.username || '',
    type_code: user?.type_code || 'U001',
  });

  const handleSave = async () => {
    setIsSaving(true);
    setMessage(null);

    try {
      // 이름 업데이트
      if (formData.username !== user?.username) {
        await api.put('/users/me', { username: formData.username });
      }

      // 타입 업데이트
      if (formData.type_code !== user?.type_code) {
        await api.put('/users/me/type', { type_code: formData.type_code });
      }

      updateUser({
        username: formData.username,
        type_code: formData.type_code as 'U001' | 'U002',
      });

      setMessage({ type: 'success', text: '프로필이 저장되었습니다.' });
      setIsEditing(false);
    } catch (err: any) {
      setMessage({
        type: 'error',
        text: err.response?.data?.detail || '저장에 실패했습니다.',
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancel = () => {
    setFormData({
      username: user?.username || '',
      type_code: user?.type_code || 'U001',
    });
    setIsEditing(false);
    setMessage(null);
  };

  return (
    <div className="p-6">
      <Typography variant="h4" color="blue-gray" className="mb-6">
        프로필
      </Typography>

      {message && (
        <Alert
          color={message.type === 'success' ? 'green' : 'red'}
          className="mb-4"
          onClose={() => setMessage(null)}
        >
          {message.text}
        </Alert>
      )}

      <Card className="max-w-2xl">
        <CardHeader floated={false} shadow={false} className="rounded-none">
          <div className="flex items-center justify-between">
            <Typography variant="h5" color="blue-gray">
              기본 정보
            </Typography>
            {!isEditing && (
              <Button size="sm" onClick={() => setIsEditing(true)}>
                수정
              </Button>
            )}
          </div>
        </CardHeader>
        <CardBody className="space-y-6">
          {/* 이메일 (수정 불가) */}
          <div>
            <Typography variant="small" color="gray" className="mb-1">
              이메일
            </Typography>
            <Input
              value={user?.google_email || ''}
              disabled
              className="!border-gray-300"
              labelProps={{ className: 'hidden' }}
            />
          </div>

          {/* 이름 */}
          <div>
            <Typography variant="small" color="gray" className="mb-1">
              이름
            </Typography>
            <Input
              value={formData.username}
              onChange={(e) => setFormData({ ...formData, username: e.target.value })}
              disabled={!isEditing}
              className="!border-gray-300"
              labelProps={{ className: 'hidden' }}
            />
          </div>

          {/* 사용자 유형 */}
          <div>
            <Typography variant="small" color="gray" className="mb-1">
              사용자 유형
            </Typography>
            {isEditing ? (
              <Select
                value={formData.type_code}
                onChange={(val) => setFormData({ ...formData, type_code: val || 'U001' })}
                className="!border-gray-300"
                labelProps={{ className: 'hidden' }}
              >
                <Option value="U001">{USER_TYPE_NAMES['U001']}</Option>
                <Option value="U002">{USER_TYPE_NAMES['U002']}</Option>
              </Select>
            ) : (
              <Input
                value={USER_TYPE_NAMES[formData.type_code] || formData.type_code}
                disabled
                className="!border-gray-300"
                labelProps={{ className: 'hidden' }}
              />
            )}
          </div>

          {/* 가입일 */}
          <div>
            <Typography variant="small" color="gray" className="mb-1">
              가입일
            </Typography>
            <Input
              value={
                user?.create_date
                  ? new Date(user.create_date).toLocaleDateString('ko-KR')
                  : '-'
              }
              disabled
              className="!border-gray-300"
              labelProps={{ className: 'hidden' }}
            />
          </div>

          {/* 버튼 */}
          {isEditing && (
            <div className="flex gap-2 pt-4">
              <Button onClick={handleSave} disabled={isSaving}>
                {isSaving ? '저장 중...' : '저장'}
              </Button>
              <Button variant="outlined" onClick={handleCancel}>
                취소
              </Button>
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  );
};

export default ProfilePage;
