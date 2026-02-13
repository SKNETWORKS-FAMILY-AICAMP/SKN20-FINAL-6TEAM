import React, { useState, useEffect } from 'react';
import {
  Card,
  CardBody,
  Typography,
  Input,
  Button,
  Dialog,
  DialogHeader,
  DialogBody,
  DialogFooter,
  Select,
  Option,
  IconButton,
  Alert,
} from '@material-tailwind/react';
import { PlusIcon, PencilIcon, TrashIcon } from '@heroicons/react/24/outline';
import { INDUSTRY_MAJOR, INDUSTRY_MINOR, INDUSTRY_ALL, COMPANY_STATUS, REGION_SIDO, REGION_SIGUNGU, PROVINCES } from '../../lib/constants';
import type { CompanyStatusKey } from '../../lib/constants';
import { RegionSelect } from '../common/RegionSelect';
import api from '../../lib/api';
import { useAuthStore } from '../../stores/authStore';
import type { Company } from '../../types';

/** Convert R-code to human-readable address (e.g. "서울특별시 강남구") */
const regionCodeToDisplayName = (code: string): string => {
  if (!code) return '';

  // Check if it's a sido-level code
  if (code in REGION_SIDO) {
    return REGION_SIDO[code];
  }

  // Find the parent sido for this sigungu code
  for (const sidoCode of PROVINCES) {
    const sigungus = REGION_SIGUNGU[sidoCode] || {};
    if (code in sigungus) {
      return `${REGION_SIDO[sidoCode]} ${sigungus[code]}`;
    }
  }

  return code;
};

/** Find R-code from a display name (reverse lookup) */
const displayNameToRegionCode = (name: string): string => {
  if (!name) return '';

  // Check if it's already an R-code
  if (name.startsWith('R') && /^R\d{7}$/.test(name)) {
    return name;
  }

  // Try to match as "시도 시군구" format
  const parts = name.split(' ');
  if (parts.length >= 2) {
    const sidoName = parts[0];
    const sigunguName = parts.slice(1).join(' ');
    for (const sidoCode of PROVINCES) {
      if (REGION_SIDO[sidoCode] === sidoName) {
        const sigungus = REGION_SIGUNGU[sidoCode] || {};
        for (const [code, sgName] of Object.entries(sigungus)) {
          if (sgName === sigunguName) return code;
        }
        return sidoCode;
      }
    }
  }

  // Try to match as sido-only
  for (const sidoCode of PROVINCES) {
    if (REGION_SIDO[sidoCode] === name) return sidoCode;
  }

  return '';
};

interface CompanyFormData {
  status: CompanyStatusKey;
  com_name: string;
  biz_num: string;
  biz_code: string;
  addr: string;
  region_code: string;
  open_date: string;
}

const INITIAL_FORM_DATA: CompanyFormData = {
  status: 'PREPARING',
  com_name: '(예비) 창업 준비',
  biz_num: '',
  biz_code: 'BA000000',
  addr: '',
  region_code: '',
  open_date: '',
};

const TABLE_HEADERS = ['회사명', '사업자번호', '업종', '주소', '개업일', '액션'];

export const CompanyForm: React.FC = () => {
  const { updateUser } = useAuthStore();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingCompany, setEditingCompany] = useState<Company | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const [formData, setFormData] = useState<CompanyFormData>(INITIAL_FORM_DATA);

  const isPreparing = formData.status === 'PREPARING';

  const fetchCompanies = async () => {
    try {
      const response = await api.get('/companies');
      setCompanies(response.data);
    } catch (err) {
      console.error('Failed to fetch companies:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchCompanies();
  }, []);

  const openCreateDialog = () => {
    setEditingCompany(null);
    setFormData(INITIAL_FORM_DATA);
    setIsDialogOpen(true);
  };

  const openEditDialog = (company: Company) => {
    setEditingCompany(company);
    const isOperating = Boolean(company.biz_num);
    const existingAddr = company.addr || '';
    setFormData({
      status: isOperating ? 'OPERATING' : 'PREPARING',
      com_name: company.com_name,
      biz_num: company.biz_num || '',
      biz_code: company.biz_code || 'BA000000',
      addr: existingAddr,
      region_code: displayNameToRegionCode(existingAddr),
      open_date: company.open_date ? company.open_date.split('T')[0] : '',
    });
    setIsDialogOpen(true);
  };

  const handleStatusChange = (val: string | undefined) => {
    const newStatus = (val as CompanyStatusKey) || 'PREPARING';
    setFormData((prev) => ({
      ...prev,
      status: newStatus,
      biz_num: newStatus === 'PREPARING' ? '' : prev.biz_num,
      com_name: newStatus === 'PREPARING' && !prev.com_name ? '(예비) 창업 준비' : prev.com_name,
    }));
  };

  const handleSave = async () => {
    setIsSaving(true);
    setMessage(null);

    try {
      const data = {
        com_name: formData.com_name,
        biz_num: isPreparing ? '' : formData.biz_num,
        biz_code: formData.biz_code,
        addr: formData.addr,
        open_date: formData.open_date ? new Date(formData.open_date).toISOString() : null,
      };
      if (editingCompany) {
        await api.put(`/companies/${editingCompany.company_id}`, data);
        setMessage({ type: 'success', text: '기업 정보가 수정되었습니다.' });
      } else {
        await api.post('/companies', data);

        // Update user type to 사업자 (U003) after successful company registration
        try {
          await api.put('/users/me/type', { type_code: 'U0000003' });
          updateUser({ type_code: 'U0000003' });
        } catch {
          // Non-critical: company was saved, type update failure is acceptable
        }

        setMessage({ type: 'success', text: '기업이 등록되었습니다.' });
      }

      setIsDialogOpen(false);
      fetchCompanies();
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

  const handleDelete = async (companyId: number) => {
    if (!window.confirm('정말 삭제하시겠습니까?')) return;

    try {
      await api.delete(`/companies/${companyId}`);
      setMessage({ type: 'success', text: '기업이 삭제되었습니다.' });
      fetchCompanies();
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      setMessage({
        type: 'error',
        text: error.response?.data?.detail || '삭제에 실패했습니다.',
      });
    }
  };

  return (
    <>
      <div className="flex items-center justify-between mb-4">
        <Typography variant="h5" color="blue-gray">
          기업 목록
        </Typography>
        <Button className="flex items-center gap-2" size="sm" onClick={openCreateDialog}>
          <PlusIcon className="h-4 w-4" />
          기업 추가
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

      {isLoading ? (
        <div className="text-center py-10">
          <Typography color="gray">로딩 중...</Typography>
        </div>
      ) : companies.length === 0 ? (
        <Card>
          <CardBody className="text-center py-10">
            <Typography color="gray">등록된 기업이 없습니다.</Typography>
            <Button className="mt-4" onClick={openCreateDialog}>
              첫 기업 등록하기
            </Button>
          </CardBody>
        </Card>
      ) : (
        <Card>
          <CardBody className="overflow-x-auto px-0">
            <table className="w-full min-w-max table-auto text-left">
              <thead>
                <tr>
                  {TABLE_HEADERS.map((head) => (
                    <th key={head} className="border-b border-blue-gray-100 bg-blue-gray-50 p-4">
                      <Typography variant="small" color="blue-gray" className="font-semibold leading-none">
                        {head}
                      </Typography>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {companies.map((company, index) => {
                  const isLast = index === companies.length - 1;
                  const rowClass = isLast ? 'p-4' : 'p-4 border-b border-blue-gray-50';
                  return (
                    <tr key={company.company_id}>
                      <td className={rowClass}>
                        <Typography variant="small" color="blue-gray" className="font-medium">
                          {company.com_name}
                        </Typography>
                      </td>
                      <td className={rowClass}>
                        <Typography variant="small" color="gray">
                          {company.biz_num || '-'}
                        </Typography>
                      </td>
                      <td className={rowClass}>
                        <Typography variant="small" color="gray">
                          {INDUSTRY_ALL[company.biz_code || ''] || company.biz_code || '-'}
                        </Typography>
                      </td>
                      <td className={rowClass}>
                        <Typography variant="small" color="gray">
                          {company.addr || '-'}
                        </Typography>
                      </td>
                      <td className={rowClass}>
                        <Typography variant="small" color="gray">
                          {company.open_date
                            ? new Date(company.open_date).toLocaleDateString('ko-KR')
                            : '-'}
                        </Typography>
                      </td>
                      <td className={rowClass}>
                        <div className="flex gap-1">
                          <IconButton variant="text" size="sm" onClick={() => openEditDialog(company)}>
                            <PencilIcon className="h-4 w-4" />
                          </IconButton>
                          <IconButton
                            variant="text"
                            size="sm"
                            color="red"
                            onClick={() => handleDelete(company.company_id)}
                          >
                            <TrashIcon className="h-4 w-4" />
                          </IconButton>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </CardBody>
        </Card>
      )}

      {/* Create/Edit Dialog */}
      <Dialog open={isDialogOpen} handler={() => setIsDialogOpen(false)} size="md">
        <DialogHeader>{editingCompany ? '기업 정보 수정' : '기업 등록'}</DialogHeader>
        <DialogBody className="space-y-4">
          {/* Company Status */}
          <div>
            <Typography variant="small" color="gray" className="mb-1">
              기업 상태 *
            </Typography>
            <Select
              value={formData.status}
              onChange={handleStatusChange}
              className="!border-gray-300"
              labelProps={{ className: 'hidden' }}
            >
              {(Object.entries(COMPANY_STATUS) as [CompanyStatusKey, string][]).map(([key, label]) => (
                <Option key={key} value={key}>
                  {label}
                </Option>
              ))}
            </Select>
          </div>

          {/* Company Name */}
          <div>
            <Typography variant="small" color="gray" className="mb-1">
              회사명 *
            </Typography>
            <Input
              value={formData.com_name}
              onChange={(e) => setFormData({ ...formData, com_name: e.target.value })}
              className="!border-gray-300"
              labelProps={{ className: 'hidden' }}
            />
          </div>

          {/* Business Registration Number */}
          <div>
            <Typography variant="small" color="gray" className="mb-1">
              사업자등록번호
            </Typography>
            <Input
              value={formData.biz_num}
              onChange={(e) => setFormData({ ...formData, biz_num: e.target.value })}
              placeholder="000-00-00000"
              disabled={isPreparing}
              className="!border-gray-300"
              label=" "
            />
          </div>

          {/* Industry - 2-tier (대분류 → 소분류) */}
          <div>
            <Typography variant="small" color="gray" className="mb-1">
              업종 (대분류)
            </Typography>
            <Select
              value={(() => {
                // Find major code from current biz_code
                for (const majorCode of Object.keys(INDUSTRY_MAJOR)) {
                  const minors = INDUSTRY_MINOR[majorCode] || {};
                  if (formData.biz_code === majorCode || formData.biz_code in minors) {
                    return majorCode;
                  }
                }
                return 'BA000000';
              })()}
              onChange={(val) => {
                const majorCode = val || 'BA000000';
                setFormData({ ...formData, biz_code: majorCode });
              }}
              className="!border-gray-300"
              labelProps={{ className: 'hidden' }}
            >
              {Object.entries(INDUSTRY_MAJOR).map(([code, name]) => (
                <Option key={code} value={code}>
                  {name}
                </Option>
              ))}
            </Select>
          </div>
          <div>
            <Typography variant="small" color="gray" className="mb-1">
              업종 (소분류)
            </Typography>
            <Select
              key={(() => {
                for (const majorCode of Object.keys(INDUSTRY_MAJOR)) {
                  const minors = INDUSTRY_MINOR[majorCode] || {};
                  if (formData.biz_code === majorCode || formData.biz_code in minors) {
                    return majorCode;
                  }
                }
                return 'BA000000';
              })()}
              value={formData.biz_code in INDUSTRY_MAJOR ? '' : formData.biz_code}
              onChange={(val) => {
                if (val) {
                  setFormData({ ...formData, biz_code: val });
                }
              }}
              className="!border-gray-300"
              labelProps={{ className: 'hidden' }}
            >
              {(() => {
                let selectedMajor = 'BA000000';
                for (const majorCode of Object.keys(INDUSTRY_MAJOR)) {
                  const minors = INDUSTRY_MINOR[majorCode] || {};
                  if (formData.biz_code === majorCode || formData.biz_code in minors) {
                    selectedMajor = majorCode;
                    break;
                  }
                }
                const minors = INDUSTRY_MINOR[selectedMajor] || {};
                return Object.entries(minors).map(([code, name]) => (
                  <Option key={code} value={code}>
                    {name}
                  </Option>
                ));
              })()}
            </Select>
          </div>

          {/* Address */}
          <div>
            <Typography variant="small" color="gray" className="mb-1">
              주소
            </Typography>
            <RegionSelect
              value={formData.region_code}
              onChange={(val) => setFormData({ ...formData, region_code: val, addr: regionCodeToDisplayName(val) })}
            />
          </div>

          {/* Open Date */}
          <div>
            <Typography variant="small" color="gray" className="mb-1">
              {isPreparing ? '사업 시작 예정일' : '개업일'}
            </Typography>
            <Input
              type="date"
              value={formData.open_date}
              onChange={(e) => setFormData({ ...formData, open_date: e.target.value })}
              className="!border-gray-300"
              labelProps={{ className: 'hidden' }}
            />
          </div>
        </DialogBody>
        <DialogFooter>
          <Button variant="text" onClick={() => setIsDialogOpen(false)}>
            취소
          </Button>
          <Button onClick={handleSave} disabled={!formData.com_name.trim() || isSaving}>
            {isSaving ? '저장 중...' : '저장'}
          </Button>
        </DialogFooter>
      </Dialog>
    </>
  );
};
