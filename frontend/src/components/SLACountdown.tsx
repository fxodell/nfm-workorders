import { useEffect, useState } from 'react';
import { getCountdown } from '@/utils/dateFormat';

interface Props {
  deadline: string;
  label: string;
}

export default function SLACountdown({ deadline, label }: Props) {
  const [countdown, setCountdown] = useState(getCountdown(deadline));

  useEffect(() => {
    const interval = setInterval(() => {
      setCountdown(getCountdown(deadline));
    }, 30000);
    return () => clearInterval(interval);
  }, [deadline]);

  const colorClass = {
    green: 'text-green-600',
    yellow: 'text-yellow-600',
    red: 'text-red-600',
  }[countdown.color];

  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-gray-500">{label}</span>
      <span className={`font-medium ${colorClass} ${countdown.pulsing ? 'animate-pulse' : ''}`}>
        {countdown.text}
      </span>
    </div>
  );
}
