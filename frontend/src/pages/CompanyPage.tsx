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
  Select,
  Option,
  IconButton,
  Alert,
} from '@material-tailwind/react';
import { PlusIcon, PencilIcon, TrashIcon } from '@heroicons/react/24/outline';
import api from '../lib/api';
import type { Company } from '../types';

const INDUSTRY_CODES: Record<string, string> = {
  B001: '음식점업',
  B002: '소매업',
  B003: '서비스업',
  B004: '제조업',
  B005: 'IT/소프트웨어',
};

const CompanyPage: React.FC = () => {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingCompany, setEditingCompany] = useState<Company | null>(null);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const [formData, setFormData] = useState({
    com_name: '',
    biz_num: '',
    addr: '',
    open_date: '',
    biz_code: 'B001',
  });

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
    setFormData({
      com_name: '',
      biz_num: '',
      addr: '',
      open_date: '',
      biz_code: 'B001',
    });
    setIsDialogOpen(true);
  };

  const openEditDialog = (company: Company) => {
    setEditingCompany(company);
    setFormData({
      com_name: company.com_name,
      biz_num: company.biz_num,
      addr: company.addr,
      open_date: company.open_date ? company.open_date.split('T')[0] : '',
      biz_code: company.biz_code || 'B001',
    });
    setIsDialogOpen(true);
  };

  const handleSave = async () => {
    try {
      const data = {
        ...formData,
        open_date: formData.open_date ? new Date(formData.open_date).toISOString() : null,
      };

      if (editingCompany) {
        await api.put(`/companies/${editingCompany.company_id}`, data);
        setMessage({ type: 'success', text: '기업 정보가 수정되었습니다.' });
      } else {
        await api.post('/companies', data);
        setMessage({ type: 'success', text: '기업이 등록되었습니다.' });
      }

      setIsDialogOpen(false);
      fetchCompanies();
    } catch (err: any) {
      setMessage({
        type: 'error',
        text: err.response?.data?.detail || '저장에 실패했습니다.',
      });
    }
  };

  const handleDelete = async (companyId: number) => {
    if (!window.confirm('정말 삭제하시겠습니까?')) return;

    try {
      await api.delete(`/companies/${companyId}`);
      setMessage({ type: 'success', text: '기업이 삭제되었습니다.' });
      fetchCompanies();
    } catch (err: any) {
      setMessage({
        type: 'error',
        text: err.response?.data?.detail || '삭제에 실패했습니다.',
      });
    }
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <Typography variant="h4" color="blue-gray">
          기업 정보
        </Typography>
        <Button className="flex items-center gap-2" onClick={openCreateDialog}>
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
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {companies.map((company) => (
            <Card key={company.company_id}>
              <CardHeader floated={false} shadow={false} className="rounded-none">
                <div className="flex items-center justify-between">
                  <Typography variant="h6" color="blue-gray">
                    {company.com_name}
                  </Typography>
                  <div className="flex gap-1">
                    <IconButton
                      variant="text"
                      size="sm"
                      onClick={() => openEditDialog(company)}
                    >
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
                </div>
              </CardHeader>
              <CardBody className="pt-0">
                <div className="space-y-2 text-sm">
                  <div>
                    <span className="text-gray-500">사업자번호:</span>{' '}
                    {company.biz_num || '-'}
                  </div>
                  <div>
                    <span className="text-gray-500">업종:</span>{' '}
                    {INDUSTRY_CODES[company.biz_code || ''] || company.biz_code || '-'}
                  </div>
                  <div>
                    <span className="text-gray-500">주소:</span>{' '}
                    {company.addr || '-'}
                  </div>
                  <div>
                    <span className="text-gray-500">개업일:</span>{' '}
                    {company.open_date
                      ? new Date(company.open_date).toLocaleDateString('ko-KR')
                      : '-'}
                  </div>
                </div>
              </CardBody>
            </Card>
          ))}
        </div>
      )}

      {/* 등록/수정 다이얼로그 */}
      <Dialog open={isDialogOpen} handler={() => setIsDialogOpen(false)} size="md">
        <DialogHeader>
          {editingCompany ? '기업 정보 수정' : '기업 등록'}
        </DialogHeader>
        <DialogBody className="space-y-4">
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
          <div>
            <Typography variant="small" color="gray" className="mb-1">
              사업자등록번호
            </Typography>
            <Input
              value={formData.biz_num}
              onChange={(e) => setFormData({ ...formData, biz_num: e.target.value })}
              placeholder="000-00-00000"
              className="!border-gray-300"
              labelProps={{ className: 'hidden' }}
            />
          </div>
          <div>
            <Typography variant="small" color="gray" className="mb-1">
              업종
            </Typography>
            <Select
              value={formData.biz_code}
              onChange={(val) => setFormData({ ...formData, biz_code: val || 'B001' })}
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
          <div>
            <Typography variant="small" color="gray" className="mb-1">
              주소
            </Typography>
            <Input
              value={formData.addr}
              onChange={(e) => setFormData({ ...formData, addr: e.target.value })}
              className="!border-gray-300"
              labelProps={{ className: 'hidden' }}
            />
          </div>
          <div>
            <Typography variant="small" color="gray" className="mb-1">
              개업일
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
          <Button onClick={handleSave} disabled={!formData.com_name.trim()}>
            저장
          </Button>
        </DialogFooter>
      </Dialog>
    </div>
  );
};

export default CompanyPage;
