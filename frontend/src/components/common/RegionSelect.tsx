import React, { useState, useEffect } from 'react';
import { Select, Option } from '@material-tailwind/react';
import { REGION_SIDO, REGION_SIGUNGU, PROVINCES } from '../../lib/constants';

interface RegionSelectProps {
  value: string;
  onChange: (val: string) => void;
  disabled?: boolean;
}

/**
 * 2-tier region select: 시/도 + 시/군/구
 * value format: R-code (e.g. "R1168000" for 서울특별시 강남구)
 */
export const RegionSelect: React.FC<RegionSelectProps> = ({ value, onChange, disabled = false }) => {
  const [sidoCode, setSidoCode] = useState('');
  const [sigunguCode, setSigunguCode] = useState('');

  // Sync local state from parent value (R-code)
  useEffect(() => {
    if (!value) {
      setSidoCode('');
      setSigunguCode('');
      return;
    }

    // Find which sido this sigungu belongs to
    for (const sido of PROVINCES) {
      const sigungus = REGION_SIGUNGU[sido] || {};
      if (value === sido) {
        setSidoCode(sido);
        setSigunguCode('');
        return;
      }
      if (value in sigungus) {
        setSidoCode(sido);
        setSigunguCode(value);
        return;
      }
    }

    setSidoCode('');
    setSigunguCode('');
  }, [value]);

  const sigunguOptions = sidoCode ? (REGION_SIGUNGU[sidoCode] || {}) : {};

  const handleSidoChange = (val: string | undefined) => {
    const newSido = val || '';
    setSidoCode(newSido);
    setSigunguCode('');
    onChange(newSido);
  };

  const handleSigunguChange = (val: string | undefined) => {
    const newSigungu = val || '';
    setSigunguCode(newSigungu);
    if (newSigungu) {
      onChange(newSigungu);
    }
  };

  return (
    <div className="grid grid-cols-2 gap-2">
      <Select
        value={sidoCode}
        onChange={handleSidoChange}
        disabled={disabled}
        className="!border-gray-300"
        labelProps={{ className: 'hidden' }}
      >
        {PROVINCES.map((code) => (
          <Option key={code} value={code}>
            {REGION_SIDO[code]}
          </Option>
        ))}
      </Select>
      <Select
        key={sidoCode}
        value={sigunguCode}
        onChange={handleSigunguChange}
        disabled={disabled || !sidoCode}
        className="!border-gray-300"
        labelProps={{ className: 'hidden' }}
      >
        {Object.entries(sigunguOptions).map(([code, name]) => (
          <Option key={code} value={code}>
            {name}
          </Option>
        ))}
      </Select>
    </div>
  );
};
