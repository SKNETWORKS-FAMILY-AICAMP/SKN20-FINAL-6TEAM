import React from 'react';
import {
  Card,
  CardBody,
  Input,
  Select,
  Option,
  Button,
} from '@material-tailwind/react';
import { MagnifyingGlassIcon } from '@heroicons/react/24/outline';
import type { AdminHistoryFilters } from '../../types';

interface HistoryFilterBarProps {
  filters: AdminHistoryFilters;
  onFiltersChange: (filters: AdminHistoryFilters) => void;
  onSearch: () => void;
}

export const HistoryFilterBar: React.FC<HistoryFilterBarProps> = ({
  filters,
  onFiltersChange,
  onSearch,
}) => {
  return (
    <Card>
      <CardBody>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Select
            label="도메인"
            value={filters.domain || ''}
            onChange={(value) => onFiltersChange({ ...filters, domain: value || undefined })}
          >
            <Option value="">전체</Option>
            <Option value="startup_funding">창업/지원</Option>
            <Option value="finance_tax">재무/세무</Option>
            <Option value="hr_labor">인사/노무</Option>
            <Option value="law_common">법률</Option>
          </Select>
          <Input
            label="최소 LLM 점수"
            type="number"
            value={filters.min_score?.toString() || ''}
            onChange={(e) =>
              onFiltersChange({
                ...filters,
                min_score: e.target.value ? parseInt(e.target.value) : undefined,
              })
            }
            crossOrigin={undefined}
          />
          <Input
            label="최대 LLM 점수"
            type="number"
            value={filters.max_score?.toString() || ''}
            onChange={(e) =>
              onFiltersChange({
                ...filters,
                max_score: e.target.value ? parseInt(e.target.value) : undefined,
              })
            }
            crossOrigin={undefined}
          />
          <Select
            label="통과 여부"
            value={
              filters.passed_only === undefined
                ? ''
                : filters.passed_only
                  ? 'true'
                  : 'false'
            }
            onChange={(value) =>
              onFiltersChange({
                ...filters,
                passed_only: value === '' ? undefined : value === 'true',
              })
            }
          >
            <Option value="">전체</Option>
            <Option value="true">통과만</Option>
            <Option value="false">실패만</Option>
          </Select>
        </div>
        <div className="mt-4 flex justify-end">
          <Button onClick={onSearch} className="flex items-center gap-2">
            <MagnifyingGlassIcon className="h-4 w-4" />
            검색
          </Button>
        </div>
      </CardBody>
    </Card>
  );
};
