import React, { useState, useEffect } from 'react';
import { Card, CardBody, Typography } from '@material-tailwind/react';

interface ResponseProgressProps {
  isLoading: boolean;
}

const PROGRESS_STAGES = [
  { text: '질문을 분석하고 있습니다', duration: 1000 },
  { text: '관련 문서를 검색하고 있습니다', duration: 1500 },
  { text: '답변을 생성하고 있습니다', duration: Infinity },
];

export const ResponseProgress: React.FC<ResponseProgressProps> = ({ isLoading }) => {
  const [stageIndex, setStageIndex] = useState(0);
  const [dots, setDots] = useState('');

  useEffect(() => {
    if (!isLoading) {
      setStageIndex(0);
      setDots('');
      return;
    }

    // Progress through stages
    let elapsed = 0;
    const stageTimer = setInterval(() => {
      elapsed += 100;
      const currentStageDuration = PROGRESS_STAGES[stageIndex]?.duration ?? Infinity;
      if (elapsed >= currentStageDuration && stageIndex < PROGRESS_STAGES.length - 1) {
        setStageIndex((prev) => Math.min(prev + 1, PROGRESS_STAGES.length - 1));
        elapsed = 0;
      }
    }, 100);

    return () => clearInterval(stageTimer);
  }, [isLoading, stageIndex]);

  // Animate dots
  useEffect(() => {
    if (!isLoading) return;

    const dotsTimer = setInterval(() => {
      setDots((prev) => (prev.length >= 3 ? '' : prev + '.'));
    }, 400);

    return () => clearInterval(dotsTimer);
  }, [isLoading]);

  if (!isLoading) return null;

  const currentStage = PROGRESS_STAGES[stageIndex];

  return (
    <div className="flex justify-start">
      <Card className="bg-white">
        <CardBody className="p-3">
          <div className="flex items-center gap-3">
            <div className="flex gap-1">
              {[0, 1, 2].map((i) => (
                <div
                  key={i}
                  className={`w-2 h-2 rounded-full transition-colors duration-300 ${
                    i <= stageIndex ? 'bg-blue-500' : 'bg-gray-300'
                  }`}
                  style={{
                    animation: i === stageIndex ? 'pulse 1s infinite' : 'none',
                  }}
                />
              ))}
            </div>
            <Typography variant="small" color="gray">
              {currentStage.text}
              <span className="inline-block w-6">{dots}</span>
            </Typography>
          </div>
          <style>
            {`
              @keyframes pulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.5; }
              }
            `}
          </style>
        </CardBody>
      </Card>
    </div>
  );
};
