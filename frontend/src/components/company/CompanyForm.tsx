import React, { forwardRef, useEffect, useImperativeHandle, useState } from 'react';
import {
  Card,
  CardBody,
  Typography,
  Input,
  Button,
  Select,
  Option,
  IconButton,
} from '@material-tailwind/react';
import { Modal } from '../common/Modal';
import { useToastStore } from '../../stores/toastStore';
import { PlusIcon, PencilIcon, TrashIcon, StarIcon as StarIconOutline } from '@heroicons/react/24/outline';
import { StarIcon as StarIconSolid } from '@heroicons/react/24/solid';
import { INDUSTRY_MAJOR, INDUSTRY_MINOR, INDUSTRY_ALL, COMPANY_STATUS, REGION_SIDO, REGION_SIGUNGU, PROVINCES } from '../../lib/constants';
import type { CompanyStatusKey } from '../../lib/constants';
import { RegionSelect } from '../common/RegionSelect';
import axios from 'axios';
import api from '../../lib/api';
import { extractErrorMessage } from '../../lib/errorHandler';
import { formatDate } from '../../lib/dateUtils';
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
  com_name: '',
  biz_num: '',
  biz_code: 'BA000000',
  addr: '',
  region_code: '',
  open_date: '',
};

const COMPANY_PAGE_SIZE = 5;

const TABLE_HEADERS = ['회사명', '사업자번호', '업종', '주소', '개업일', '액션'];

interface CompanyFormProps {
  selectedCompanyId?: number | null;
  onSelectCompany?: (company: Company | null) => void;
  showTopAddButton?: boolean;
}

export interface CompanyFormHandle {
  openCreateDialog: () => void;
}

export const CompanyForm = forwardRef<CompanyFormHandle, CompanyFormProps>(({
  selectedCompanyId = null,
  onSelectCompany,
  showTopAddButton = true,
}, ref) => {
  const { updateUser, user } = useAuthStore();
  const addToast = useToastStore((s) => s.addToast);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingCompany, setEditingCompany] = useState<Company | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  const [formData, setFormData] = useState<CompanyFormData>(INITIAL_FORM_DATA);

  const isPreparing = formData.status === 'PREPARING';
  const isAdmin = user?.type_code === 'U0000001';
  const totalPages = Math.max(1, Math.ceil(companies.length / COMPANY_PAGE_SIZE));
  const pageStartIndex = (currentPage - 1) * COMPANY_PAGE_SIZE;
  const paginatedCompanies = companies.slice(pageStartIndex, pageStartIndex + COMPANY_PAGE_SIZE);

  useEffect(() => {
    setCurrentPage((prev) => Math.min(prev, totalPages));
  }, [totalPages]);

  const fetchCompanies = async () => {
    try {
      const response = await api.get('/companies');
      const fetchedCompanies: Company[] = response.data;
      setCompanies(fetchedCompanies);

      if (selectedCompanyId != null) {
        const matchedCompany =
          fetchedCompanies.find((company) => company.company_id === selectedCompanyId) ?? null;
        onSelectCompany?.(matchedCompany);
      } else {
        const mainCompany = fetchedCompanies.find((c) => c.main_yn) ?? null;
        onSelectCompany?.(mainCompany);
      }
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
    setFormData({
      ...INITIAL_FORM_DATA,
      open_date: new Date().toISOString().split('T')[0],
    });
    setIsDialogOpen(true);
  };

  useImperativeHandle(ref, () => ({
    openCreateDialog,
  }));

  const openEditDialog = (company: Company) => {
    onSelectCompany?.(company);
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
      open_date: company.open_date ? company.open_date.split('T')[0] : new Date().toISOString().split('T')[0],
    });
    setIsDialogOpen(true);
  };

  const handleStatusChange = (val: string | undefined) => {
    const newStatus = (val as CompanyStatusKey) || 'PREPARING';
    setFormData((prev) => ({
      ...prev,
      status: newStatus,
      biz_num: newStatus === 'PREPARING' ? '' : prev.biz_num,
    }));
  };

  const handleSave = async () => {
    setIsSaving(true);

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
        onSelectCompany?.({
          ...editingCompany,
          ...data,
          open_date: data.open_date ?? undefined,
        } as Company);
        addToast({ type: 'success', message: '기업 정보가 수정되었습니다.' });
      } else {
        await api.post('/companies', data);

        // 사업자번호가 있으면 사용자 유형을 사업자로 변경 (관리자 보호는 백엔드에서 처리)
        if (formData.biz_num) {
          try {
            await api.put('/users/me/type', { type_code: 'U0000003' });
            updateUser({ type_code: 'U0000003' });
          } catch {
            // Non-critical: company was saved, type update failure is acceptable
          }
        }

        addToast({ type: 'success', message: '기업이 등록되었습니다.' });
      }

      setIsDialogOpen(false);
      fetchCompanies();
    } catch (err: unknown) {
      if (isAdmin && axios.isAxiosError(err) && err.response?.data) {
        addToast({ type: 'error', message: JSON.stringify(err.response.data, null, 2) });
      } else {
        addToast({ type: 'error', message: extractErrorMessage(err, '저장에 실패했습니다.') });
      }
    } finally {
      setIsSaving(false);
    }
  };

  const handleToggleMain = async (companyId: number) => {
    try {
      await api.patch(`/companies/${companyId}/main`);
      await fetchCompanies();
    } catch (err) {
      addToast({ type: 'error', message: extractErrorMessage(err, '대표 기업 설정에 실패했습니다.') });
    }
  };

  const handleDelete = async (companyId: number) => {
    if (!window.confirm('정말 삭제하시겠습니까?')) return;

    try {
      await api.delete(`/companies/${companyId}`);
      addToast({ type: 'success', message: '기업이 삭제되었습니다.' });

      const response = await api.get('/companies');
      const remaining: Company[] = response.data;
      setCompanies(remaining);
      if (selectedCompanyId === companyId) {
        onSelectCompany?.(null);
      }

      if (user?.type_code === 'U0000003') {
        const hasBizNum = remaining.some((c) => c.biz_num);
        if (!hasBizNum) {
          try {
            await api.put('/users/me/type', { type_code: 'U0000002' });
            updateUser({ type_code: 'U0000002' });
          } catch { /* non-critical */ }
        }
      }
    } catch (err: unknown) {
      addToast({ type: 'error', message: extractErrorMessage(err, '삭제에 실패했습니다.') });
    }
  };

  return (
    <>
      {showTopAddButton && (
      <div className="mb-4 flex items-center gap-3">
        <Button className="flex items-center gap-2" size="sm" onClick={openCreateDialog}>
          <PlusIcon className="h-4 w-4" />
          기업 추가
        </Button>
      </div>
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
          <CardBody className="overflow-x-auto p-0">
            <table className="w-full min-w-max table-auto text-left">
              <thead>
                <tr>
                  {TABLE_HEADERS.map((head) => (
                    <th key={head} className="border-b border-blue-gray-100 bg-blue-gray-50 p-4 first:rounded-tl-xl last:rounded-tr-xl">
                      <Typography variant="small" color="blue-gray" className="font-semibold leading-none !text-gray-900">
                        {head}
                      </Typography>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {paginatedCompanies.map((company, index) => {
                  const isLast = index === paginatedCompanies.length - 1;
                  const rowClass = isLast ? 'p-4' : 'p-4 border-b border-blue-gray-50';
                  const isSelected = selectedCompanyId === company.company_id;
                  return (
                    <tr
                      key={company.company_id}
                      onClick={() => onSelectCompany?.(company)}
                      aria-selected={isSelected}
                      className={`cursor-pointer transition-colors ${
                        isSelected
                          ? 'bg-blue-50 shadow-[inset_4px_0_0_0_rgb(59,130,246)] hover:bg-blue-100/70'
                          : 'hover:bg-blue-gray-50'
                      }`}
                    >
                      <td className={rowClass}>
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleToggleMain(company.company_id);
                            }}
                            className="flex-shrink-0 hover:scale-110 transition-transform"
                            title={company.main_yn ? '대표 기업 해제' : '대표 기업으로 설정'}
                          >
                            {company.main_yn ? (
                              <StarIconSolid className="h-5 w-5 text-yellow-500" />
                            ) : (
                              <StarIconOutline className="h-5 w-5 text-gray-400 hover:text-yellow-400" />
                            )}
                          </button>
                          <Typography
                            variant="small"
                            color="blue-gray"
                            className={`font-medium ${isSelected ? '!text-blue-700' : '!text-gray-900'}`}
                          >
                            {company.com_name}
                          </Typography>
                        </div>
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
                            ? formatDate(company.open_date)
                            : '-'}
                        </Typography>
                      </td>
                      <td className={rowClass}>
                        <div className="flex gap-1">
                          <IconButton
                            variant="text"
                            size="sm"
                            onClick={(event) => {
                              event.stopPropagation();
                              openEditDialog(company);
                            }}
                          >
                            <PencilIcon className="h-4 w-4" />
                          </IconButton>
                          <IconButton
                            variant="text"
                            size="sm"
                            color="red"
                            onClick={(event) => {
                              event.stopPropagation();
                              handleDelete(company.company_id);
                            }}
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
            {companies.length > COMPANY_PAGE_SIZE && (
              <div className="flex items-center justify-between border-t border-blue-gray-50 px-4 py-3">
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="outlined"
                    className="px-3 py-1"
                    disabled={currentPage === 1}
                    onClick={() => setCurrentPage((prev) => Math.max(1, prev - 1))}
                  >
                    이전
                  </Button>
                  <Typography variant="small" color="blue-gray" className="min-w-[64px] text-center !text-gray-900">
                    {currentPage} / {totalPages}
                  </Typography>
                  <Button
                    size="sm"
                    variant="outlined"
                    className="px-3 py-1"
                    disabled={currentPage === totalPages}
                    onClick={() => setCurrentPage((prev) => Math.min(totalPages, prev + 1))}
                  >
                    다음
                  </Button>
                </div>
              </div>
            )}
          </CardBody>
        </Card>
      )}

      {/* Create/Edit Dialog */}
      <Modal
        open={isDialogOpen}
        onClose={() => setIsDialogOpen(false)}
        title={editingCompany ? '기업 정보 수정' : '기업 등록'}
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="text" onClick={() => setIsDialogOpen(false)}>
              취소
            </Button>
            <Button onClick={handleSave} disabled={!formData.com_name.trim() || isSaving}>
              {isSaving ? '저장 중...' : '저장'}
            </Button>
          </div>
        }
      >
        <div className="space-y-4">
          {/* Company Status */}
          <div>
            <Typography variant="small" color="gray" className="mb-1 !text-gray-700">
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
            <Typography variant="small" color="gray" className="mb-1 !text-gray-700">
              회사명 *
            </Typography>
            <Input
              value={formData.com_name}
              onChange={(e) => setFormData({ ...formData, com_name: e.target.value })}
              id="company-name-input"
              placeholder={isPreparing ? '(예비) 창업 준비' : '회사명을 입력하세요'}
              className="!border-gray-300"
              labelProps={{ className: 'hidden' }}
            />
          </div>

          {/* Business Registration Number */}
          <div>
            <Typography variant="small" color="gray" className="mb-1 !text-gray-700">
              사업자등록번호
            </Typography>
            <Input
              value={formData.biz_num}
              onChange={(e) => setFormData({ ...formData, biz_num: e.target.value })}
              placeholder="000-00-00000"
              disabled={isPreparing}
              className="!border-gray-300"
              labelProps={{ className: 'hidden' }}
            />
          </div>

          {/* Industry - 2-tier (대분류 → 소분류) */}
          <div>
            <Typography variant="small" color="gray" className="mb-1 !text-gray-700">
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
            <Typography variant="small" color="gray" className="mb-1 !text-gray-700">
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
            <Typography variant="small" color="gray" className="mb-1 !text-gray-700">
              주소
            </Typography>
            <RegionSelect
              value={formData.region_code}
              onChange={(val) => setFormData({ ...formData, region_code: val, addr: regionCodeToDisplayName(val) })}
            />
          </div>

          {/* Open Date */}
          <div>
            <Typography variant="small" color="gray" className="mb-1 !text-gray-700">
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
        </div>
      </Modal>
    </>
  );
});

CompanyForm.displayName = 'CompanyForm';
