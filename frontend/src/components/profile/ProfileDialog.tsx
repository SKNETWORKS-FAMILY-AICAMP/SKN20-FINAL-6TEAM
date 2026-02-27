import React, { useState, useEffect, useMemo } from 'react';
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
import { DEFAULT_NOTIFICATION_SETTINGS } from '../../lib/constants';
import { updateNotificationSettings } from '../../lib/userApi';
import type { NotificationSettings, User } from '../../types';
import { USER_TYPE_NAMES } from '../../types';
import api from '../../lib/api';
import { extractErrorMessage } from '../../lib/errorHandler';
import { formatDate } from '../../lib/dateUtils';

interface ProfileDialogProps {
  open: boolean;
  onClose: () => void;
}

type ProfileTab = 'profile' | 'notifications';
type BirthPartKey = 'birthYear' | 'birthMonth' | 'birthDay';
const ALERT_AUTO_DISMISS_MS = 3000;

interface BirthParts {
  birthYear: string;
  birthMonth: string;
  birthDay: string;
}

const NOTIFICATION_TOGGLE_ITEMS: Array<{
  key: keyof NotificationSettings;
  label: string;
  description: string;
}> = [
  {
    key: 'schedule_d7',
    label: 'D-7 알림',
    description: '공고 마감 7일 전 알림을 받습니다.',
  },
  {
    key: 'schedule_d3',
    label: 'D-3 알림',
    description: '공고 마감 3일 전 긴급 알림을 받습니다.',
  },
  {
    key: 'new_announce',
    label: '신규 공고 알림',
    description: '로그인/로그아웃 sync 시 신규 공고 요약 알림을 받습니다.',
  },
  {
    key: 'answer_complete',
    label: '답변 완료 알림',
    description: '백그라운드 탭에서 답변 완료 시 알림을 받습니다.',
  },
];

const toBirthInputValue = (value?: string): string => {
  if (typeof value !== 'string' || value.length < 10) {
    return '';
  }

  return value.slice(0, 10);
};

const toBirthRequestValue = (value: string): string | null => {
  if (!value) {
    return null;
  }

  return `${value}T00:00:00`;
};

const parseBirthParts = (value?: string): BirthParts => {
  const normalized = toBirthInputValue(value);
  if (!normalized) {
    return {
      birthYear: '',
      birthMonth: '',
      birthDay: '',
    };
  }

  const [birthYear = '', birthMonth = '', birthDay = ''] = normalized.split('-');
  return {
    birthYear,
    birthMonth,
    birthDay,
  };
};

const getBirthMaxDay = (birthYear: string, birthMonth: string): number => {
  const year = Number(birthYear);
  const month = Number(birthMonth);
  if (!Number.isInteger(year) || !Number.isInteger(month) || month < 1 || month > 12) {
    return 31;
  }

  return new Date(year, month, 0).getDate();
};

const formatBirthDay = (value: number): string => String(value).padStart(2, '0');

const buildBirthInputValue = (parts: BirthParts): string => {
  const { birthYear, birthMonth, birthDay } = parts;
  if (!birthYear || !birthMonth || !birthDay) {
    return '';
  }

  const maxDay = getBirthMaxDay(birthYear, birthMonth);
  const day = Number(birthDay);
  if (!Number.isInteger(day) || day < 1 || day > maxDay) {
    return '';
  }

  return `${birthYear}-${birthMonth}-${formatBirthDay(day)}`;
};

export const ProfileDialog: React.FC<ProfileDialogProps> = ({ open, onClose }) => {
  const navigate = useNavigate();
  const {
    user,
    updateUser,
    logout,
    notificationSettings: authNotificationSettings,
    setNotificationSettings: setAuthNotificationSettings,
  } = useAuthStore();
  const [activeTab, setActiveTab] = useState<ProfileTab>('profile');
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(
    null
  );
  const [notificationMessage, setNotificationMessage] = useState<{
    type: 'success' | 'error';
    text: string;
  } | null>(null);
  const [isNotificationSaving, setIsNotificationSaving] = useState(false);

  const birthYearOptions = useMemo(() => {
    const currentYear = new Date().getFullYear();
    const options: string[] = [];
    for (let year = currentYear; year >= 1900; year -= 1) {
      options.push(String(year));
    }
    return options;
  }, []);

  const birthMonthOptions = useMemo(
    () => Array.from({ length: 12 }, (_, index) => formatBirthDay(index + 1)),
    []
  );

  const [formData, setFormData] = useState({
    username: user?.username || '',
    ...parseBirthParts(user?.birth),
    type_code: user?.type_code || 'U0000001',
  });
  const [notificationForm, setNotificationForm] = useState<NotificationSettings>({
    ...DEFAULT_NOTIFICATION_SETTINGS,
  });

  // Sync form data when dialog opens or user changes
  useEffect(() => {
    if (!open || !user) {
      return;
    }

    setFormData({
      username: user.username || '',
      ...parseBirthParts(user.birth),
      type_code: user.type_code || 'U0000001',
    });
    setNotificationForm({
      ...DEFAULT_NOTIFICATION_SETTINGS,
      ...authNotificationSettings,
    });
    setActiveTab('profile');
    setIsEditing(false);
    setMessage(null);
    setNotificationMessage(null);

    let isMounted = true;
    const syncProfile = async () => {
      try {
        const response = await api.get('/users/me');
        const profile = response.data as Partial<User>;
        if (!isMounted) {
          return;
        }

        updateUser({
          birth: profile.birth ?? undefined,
          age: typeof profile.age === 'number' ? profile.age : undefined,
          create_date: profile.create_date ?? undefined,
        });

        setFormData((prev) => ({
          ...prev,
          ...parseBirthParts(profile.birth),
        }));
      } catch {
        // 모달 표시를 막지 않기 위해 프로필 상세 조회 실패는 무시합니다.
      }
    };

    void syncProfile();

    return () => {
      isMounted = false;
    };
  }, [open, user?.user_id, updateUser]);

  useEffect(() => {
    if (!message) {
      return;
    }

    const timer = setTimeout(() => {
      setMessage(null);
    }, ALERT_AUTO_DISMISS_MS);

    return () => {
      clearTimeout(timer);
    };
  }, [message]);

  useEffect(() => {
    if (!notificationMessage) {
      return;
    }

    const timer = setTimeout(() => {
      setNotificationMessage(null);
    }, ALERT_AUTO_DISMISS_MS);

    return () => {
      clearTimeout(timer);
    };
  }, [notificationMessage]);

  const handleSave = async () => {
    setIsSaving(true);
    setMessage(null);

    try {
      const currentUsername = user?.username || '';
      const currentBirth = toBirthInputValue(user?.birth);
      const nextBirth = buildBirthInputValue(formData);
      const profilePayload: {
        username?: string;
        birth?: string | null;
      } = {};

      if (formData.username !== currentUsername) {
        profilePayload.username = formData.username;
      }

      if (nextBirth !== currentBirth) {
        profilePayload.birth = toBirthRequestValue(nextBirth);
      }

      if (Object.keys(profilePayload).length > 0) {
        const profileResponse = await api.put('/users/me', profilePayload);
        const updated = profileResponse.data as {
          username?: string;
          birth?: string | null;
          age?: number | null;
        };
        updateUser({
          username: updated.username ?? formData.username,
          birth: updated.birth ?? undefined,
          age: typeof updated.age === 'number' ? updated.age : undefined,
        });
      }

      if (formData.type_code !== user?.type_code) {
        await api.put('/users/me/type', { type_code: formData.type_code });
        updateUser({
          type_code: formData.type_code as 'U0000001' | 'U0000002' | 'U0000003',
        });
      }

      setMessage({ type: 'success', text: '프로필이 저장되었습니다.' });
      setIsEditing(false);
    } catch (err: unknown) {
      setMessage({
        type: 'error',
        text: extractErrorMessage(err, '저장에 실패했습니다.'),
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancel = () => {
    setFormData({
      username: user?.username || '',
      ...parseBirthParts(user?.birth),
      type_code: user?.type_code || 'U0000001',
    });
    setIsEditing(false);
    setMessage(null);
  };

  const birthDayOptions = useMemo(() => {
    const maxDay = getBirthMaxDay(formData.birthYear, formData.birthMonth);
    return Array.from({ length: maxDay }, (_, index) => formatBirthDay(index + 1));
  }, [formData.birthYear, formData.birthMonth]);

  const handleBirthPartChange = (field: BirthPartKey, value: string) => {
    setFormData((prev) => {
      const next = {
        ...prev,
        [field]: value,
      };

      if ((field === 'birthYear' || field === 'birthMonth') && next.birthDay) {
        const maxDay = getBirthMaxDay(next.birthYear, next.birthMonth);
        if (Number(next.birthDay) > maxDay) {
          next.birthDay = formatBirthDay(maxDay);
        }
      }

      return next;
    });
  };

  const handleNotificationChange = (
    key: keyof NotificationSettings,
    value: boolean
  ) => {
    setNotificationForm((prev) => {
      if (prev[key] === value) {
        return prev;
      }

      return {
        ...prev,
        [key]: value,
      };
    });
    setNotificationMessage(null);
  };

  const handleNotificationSave = async () => {
    setIsNotificationSaving(true);
    setNotificationMessage(null);

    try {
      const saved = await updateNotificationSettings(notificationForm);
      setAuthNotificationSettings(saved);
      setNotificationForm(saved);
      setNotificationMessage({ type: 'success', text: '알림 설정이 저장되었습니다.' });
    } catch (err: unknown) {
      setNotificationMessage({
        type: 'error',
        text: extractErrorMessage(err, '알림 설정 저장에 실패했습니다.'),
      });
    } finally {
      setIsNotificationSaving(false);
    }
  };

  const handleWithdraw = async () => {
    if (!window.confirm('정말 탈퇴하시겠습니까? 이 작업은 되돌릴 수 없습니다.')) return;

    try {
      await api.delete('/users/me');
      await logout();
      onClose();
      navigate('/login');
    } catch (err: unknown) {
      setMessage({
        type: 'error',
        text: extractErrorMessage(err, '회원탈퇴에 실패했습니다.'),
      });
    }
  };

  return (
    <Dialog open={open} handler={onClose} size="md">
      <DialogHeader>
        <div className="flex items-center justify-between w-full">
          <Typography variant="h5" color="blue-gray" className="!text-gray-900">
            {activeTab === 'profile' ? '프로필' : '알림 설정'}
          </Typography>
        </div>
      </DialogHeader>
      <DialogBody className="space-y-6">
        <div className="rounded-lg border border-gray-200 p-1">
          <div className="grid grid-cols-2 gap-1">
            <button
              type="button"
              onClick={() => setActiveTab('profile')}
              className={`rounded-md px-3 py-2 text-sm transition-colors ${
                activeTab === 'profile'
                  ? 'bg-blue-50 font-semibold text-blue-700'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              프로필
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('notifications')}
              className={`rounded-md px-3 py-2 text-sm transition-colors ${
                activeTab === 'notifications'
                  ? 'bg-blue-50 font-semibold text-blue-700'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              알림 설정
            </button>
          </div>
        </div>

        {activeTab === 'profile' ? (
          <>
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
              <Typography variant="small" color="gray" className="mb-1 !text-gray-700">
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
              <Typography variant="small" color="gray" className="mb-1 !text-gray-700">
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
              <Typography variant="small" color="gray" className="mb-1 !text-gray-700">
                사용자 유형
              </Typography>
              {isEditing && user?.type_code !== 'U0000001' ? (
                <Select
                  value={formData.type_code}
                  onChange={(val: string | undefined) =>
                    setFormData({
                      ...formData,
                      type_code: (val || 'U0000001') as typeof formData.type_code,
                    })
                  }
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

            {/* Birth Date */}
            <div>
              <Typography variant="small" color="gray" className="mb-1 !text-gray-700">
                생년월일
              </Typography>
              <div className="flex items-center gap-2">
                <select
                  value={formData.birthYear}
                  onChange={(e) => handleBirthPartChange('birthYear', e.target.value)}
                  disabled={!isEditing}
                  className="h-10 min-w-0 flex-1 rounded-md border border-gray-300 bg-white px-3 text-sm text-gray-900 disabled:bg-gray-50 disabled:text-gray-500"
                >
                  <option value="">년도</option>
                  {birthYearOptions.map((year) => (
                    <option key={year} value={year}>
                      {year}
                    </option>
                  ))}
                </select>
                <select
                  value={formData.birthMonth}
                  onChange={(e) => handleBirthPartChange('birthMonth', e.target.value)}
                  disabled={!isEditing}
                  className="h-10 min-w-0 w-24 rounded-md border border-gray-300 bg-white px-3 text-sm text-gray-900 disabled:bg-gray-50 disabled:text-gray-500"
                >
                  <option value="">월</option>
                  {birthMonthOptions.map((month) => (
                    <option key={month} value={month}>
                      {month}
                    </option>
                  ))}
                </select>
                <select
                  value={formData.birthDay}
                  onChange={(e) => handleBirthPartChange('birthDay', e.target.value)}
                  disabled={!isEditing}
                  className="h-10 min-w-0 w-24 rounded-md border border-gray-300 bg-white px-3 text-sm text-gray-900 disabled:bg-gray-50 disabled:text-gray-500"
                >
                  <option value="">일</option>
                  {birthDayOptions.map((day) => (
                    <option key={day} value={day}>
                      {day}
                    </option>
                  ))}
                </select>
                {isEditing && (
                  <Button
                    type="button"
                    variant="text"
                    color="red"
                    onClick={() =>
                      setFormData((prev) => ({
                        ...prev,
                        birthYear: '',
                        birthMonth: '',
                        birthDay: '',
                      }))
                    }
                    disabled={!formData.birthYear && !formData.birthMonth && !formData.birthDay}
                  >
                    삭제
                  </Button>
                )}
              </div>
            </div>

            {/* Join Date (read-only) */}
            <div>
              <Typography variant="small" color="gray" className="mb-1 !text-gray-700">
                가입일
              </Typography>
              <Input
                value={user?.create_date ? formatDate(user.create_date) : '-'}
                disabled
                className="!border-gray-300"
                labelProps={{ className: 'hidden' }}
              />
            </div>
          </>
        ) : (
          <>
            {notificationMessage && (
              <Alert
                color={notificationMessage.type === 'success' ? 'green' : 'red'}
                onClose={() => setNotificationMessage(null)}
              >
                {notificationMessage.text}
              </Alert>
            )}
            <div className="space-y-3">
              {NOTIFICATION_TOGGLE_ITEMS.map((item) => (
                <div
                  key={item.key}
                  className="flex items-start justify-between rounded-lg border border-gray-200 px-3 py-2"
                >
                  <div className="pr-3">
                    <Typography variant="small" className="font-medium !text-gray-900">
                      {item.label}
                    </Typography>
                    <Typography variant="small" className="mt-1 !text-xs !text-gray-600">
                      {item.description}
                    </Typography>
                  </div>
                  <div className="mt-1 inline-flex overflow-hidden rounded-md border border-gray-300">
                    <button
                      type="button"
                      className={`px-3 py-1 text-xs font-semibold transition-colors ${
                        notificationForm[item.key]
                          ? 'bg-blue-600 text-white'
                          : 'bg-white text-gray-600 hover:bg-gray-50'
                      }`}
                      onClick={() => handleNotificationChange(item.key, true)}
                      aria-pressed={notificationForm[item.key]}
                    >
                      ON
                    </button>
                    <button
                      type="button"
                      className={`border-l border-gray-300 px-3 py-1 text-xs font-semibold transition-colors ${
                        !notificationForm[item.key]
                          ? 'bg-blue-600 text-white'
                          : 'bg-white text-gray-600 hover:bg-gray-50'
                      }`}
                      onClick={() => handleNotificationChange(item.key, false)}
                      aria-pressed={!notificationForm[item.key]}
                    >
                      OFF
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </DialogBody>
      <DialogFooter className="flex justify-between">
        {activeTab === 'profile' ? (
          <Button variant="text" color="red" onClick={handleWithdraw}>
            회원탈퇴
          </Button>
        ) : (
          <Button variant="text" onClick={onClose}>
            닫기
          </Button>
        )}
        {activeTab === 'profile' ? (
          isEditing ? (
            <div className="flex gap-2">
              <Button variant="outlined" onClick={handleCancel}>
                취소
              </Button>
              <Button onClick={handleSave} disabled={isSaving}>
                {isSaving ? '저장 중...' : '저장'}
              </Button>
            </div>
          ) : (
            <div className="flex gap-2">
              <Button variant="outlined" onClick={() => setIsEditing(true)}>
                수정
              </Button>
              <Button variant="text" onClick={onClose}>
                닫기
              </Button>
            </div>
          )
        ) : (
          <div className="flex gap-2">
            <Button onClick={handleNotificationSave} disabled={isNotificationSaving}>
              {isNotificationSaving ? '저장 중...' : '저장'}
            </Button>
          </div>
        )}
      </DialogFooter>
    </Dialog>
  );
};
