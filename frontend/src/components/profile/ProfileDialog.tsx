import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Dialog,
  DialogHeader,
  DialogBody,
  DialogFooter,
  Typography,
  Input,
  Button,
  Select,
  Option,
  Alert,
} from '@material-tailwind/react';
import { useAuthStore } from '../../stores/authStore';
import { USER_TYPE_NAMES } from '../../types';
import api from '../../lib/api';

interface ProfileDialogProps {
  open: boolean;
  onClose: () => void;
}

export const ProfileDialog: React.FC<ProfileDialogProps> = ({ open, onClose }) => {
  const navigate = useNavigate();
  const { user, updateUser, logout } = useAuthStore();
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const [formData, setFormData] = useState({
    username: user?.username || '',
    type_code: user?.type_code || 'U0000001',
  });

  // Sync form data when dialog opens or user changes
  useEffect(() => {
    if (open && user) {
      setFormData({
        username: user.username || '',
        type_code: user.type_code || 'U0000001',
      });
      setIsEditing(false);
      setMessage(null);
    }
  }, [open, user]);

  const handleSave = async () => {
    setIsSaving(true);
    setMessage(null);

    try {
      if (formData.username !== user?.username) {
        await api.put('/users/me', { username: formData.username });
      }

      if (formData.type_code !== user?.type_code) {
        await api.put('/users/me/type', { type_code: formData.type_code });
      }

      updateUser({
        username: formData.username,
        type_code: formData.type_code as 'U0000001' | 'U0000002' | 'U0000003',
      });

      setMessage({ type: 'success', text: '프로필이 저장되었습니다.' });
      setIsEditing(false);
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

  const handleCancel = () => {
    setFormData({
      username: user?.username || '',
      type_code: user?.type_code || 'U0000001',
    });
    setIsEditing(false);
    setMessage(null);
  };

  const handleWithdraw = async () => {
    if (!window.confirm('정말 탈퇴하시겠습니까? 이 작업은 되돌릴 수 없습니다.')) return;

    try {
      await api.delete('/users/me');
      logout();
      onClose();
      navigate('/guest');
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      setMessage({
        type: 'error',
        text: error.response?.data?.detail || '회원탈퇴에 실패했습니다.',
      });
    }
  };

  return (
    <Dialog open={open} handler={onClose} size="md">
      <DialogHeader>
        <div className="flex items-center justify-between w-full">
          <Typography variant="h5" color="blue-gray">
            프로필
          </Typography>
          {!isEditing && (
            <Button size="sm" onClick={() => setIsEditing(true)}>
              수정
            </Button>
          )}
        </div>
      </DialogHeader>
      <DialogBody className="space-y-6">
        {message && (
          <Alert
            color={message.type === 'success' ? 'green' : 'red'}
            onClose={() => setMessage(null)}
          >
            {message.text}
          </Alert>
        )}

        {/* Email (read-only) */}
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

        {/* Name */}
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

        {/* User Type */}
        <div>
          <Typography variant="small" color="gray" className="mb-1">
            사용자 유형
          </Typography>
          {isEditing ? (
            <Select
              value={formData.type_code}
              onChange={(val) => setFormData({ ...formData, type_code: val || 'U0000001' })}
              className="!border-gray-300"
              labelProps={{ className: 'hidden' }}
            >
              <Option value="U0000001">{USER_TYPE_NAMES['U0000001']}</Option>
              <Option value="U0000002">{USER_TYPE_NAMES['U0000002']}</Option>
              <Option value="U0000003">{USER_TYPE_NAMES['U0000003']}</Option>
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

        {/* Join Date (read-only) */}
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
      </DialogBody>
      <DialogFooter className="flex justify-between">
        <Button variant="text" color="red" onClick={handleWithdraw}>
          회원탈퇴
        </Button>
        {isEditing ? (
          <div className="flex gap-2">
            <Button variant="outlined" onClick={handleCancel}>
              취소
            </Button>
            <Button onClick={handleSave} disabled={isSaving}>
              {isSaving ? '저장 중...' : '저장'}
            </Button>
          </div>
        ) : (
          <Button variant="text" onClick={onClose}>
            닫기
          </Button>
        )}
      </DialogFooter>
    </Dialog>
  );
};
