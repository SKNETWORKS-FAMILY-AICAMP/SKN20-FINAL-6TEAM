import React from 'react';

interface MetricCardProps {
  label: string;
  value: number;
  unit?: string;
  /** 이 값 초과 시 경고 색상 (기본 90) */
  threshold?: number;
  subtitle?: string;
}

/**
 * 단일 리소스 수치를 표시하는 카드 컴포넌트.
 * threshold 초과 시 배경이 빨간색으로 변합니다.
 */
const MetricCard: React.FC<MetricCardProps> = ({
  label,
  value,
  unit = '%',
  threshold = 90,
  subtitle,
}) => {
  const isWarning = value > threshold;
  const isHigh = value > 75;

  const valueColor = isWarning
    ? 'text-red-600'
    : isHigh
    ? 'text-yellow-600'
    : 'text-blue-600';

  const bgColor = isWarning ? 'bg-red-50 border-red-200' : 'bg-white border-gray-200';

  return (
    <div className={`rounded-lg border p-4 text-center ${bgColor}`}>
      <p className="text-sm text-gray-500 mb-1">{label}</p>
      <p className={`text-3xl font-bold ${valueColor}`}>
        {value.toFixed(1)}
        <span className="text-lg font-normal ml-0.5">{unit}</span>
      </p>
      {subtitle && <p className="text-xs text-gray-400 mt-1">{subtitle}</p>}
      {isWarning && (
        <p className="text-xs text-red-500 mt-1 font-medium">⚠ 임계치 초과</p>
      )}
    </div>
  );
};

export default MetricCard;
