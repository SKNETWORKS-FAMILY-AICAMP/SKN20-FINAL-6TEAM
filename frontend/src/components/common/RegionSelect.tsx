import React, { useState, useEffect } from 'react';
import { Select, Option } from '@material-tailwind/react';
import { REGION_DATA, PROVINCES } from '../../lib/constants';

interface RegionSelectProps {
  value: string;
  onChange: (val: string) => void;
  disabled?: boolean;
}

/**
 * 2-tier region select: 시/도 + 시/군/구
 * value format: "시/도 시/군/구" (e.g. "서울특별시 강남구")
 */
export const RegionSelect: React.FC<RegionSelectProps> = ({ value, onChange, disabled = false }) => {
  const [province, setProvince] = useState('');
  const [district, setDistrict] = useState('');

  // Sync local state from parent value
  useEffect(() => {
    if (!value) {
      setProvince('');
      setDistrict('');
      return;
    }

    for (const prov of PROVINCES) {
      if (value.startsWith(prov)) {
        const remaining = value.slice(prov.length).trim();
        const districts = REGION_DATA[prov] || [];
        setProvince(prov);
        setDistrict(remaining && districts.includes(remaining) ? remaining : '');
        return;
      }
    }

    setProvince('');
    setDistrict('');
  }, [value]);

  const districtOptions = province ? (REGION_DATA[province] || []) : [];

  const handleProvinceChange = (val: string | undefined) => {
    const newProvince = val || '';
    setProvince(newProvince);
    setDistrict('');
    onChange(newProvince);
  };

  const handleDistrictChange = (val: string | undefined) => {
    const newDistrict = val || '';
    setDistrict(newDistrict);
    if (province && newDistrict) {
      onChange(`${province} ${newDistrict}`);
    }
  };

  return (
    <div className="grid grid-cols-2 gap-2">
      <Select
        value={province}
        onChange={handleProvinceChange}
        disabled={disabled}
        className="!border-gray-300"
        labelProps={{ className: 'hidden' }}
      >
        {PROVINCES.map((prov) => (
          <Option key={prov} value={prov}>
            {prov}
          </Option>
        ))}
      </Select>
      <Select
        key={province}
        value={district}
        onChange={handleDistrictChange}
        disabled={disabled || !province}
        className="!border-gray-300"
        labelProps={{ className: 'hidden' }}
      >
        {districtOptions.map((dist) => (
          <Option key={dist} value={dist}>
            {dist}
          </Option>
        ))}
      </Select>
    </div>
  );
};
