import { useEffect, useState } from 'react';
import { Clock } from 'lucide-react';
import { getETACountdown } from '@/utils/dateFormat';

interface Props {
  etaMinutes: number;
  acceptedAt: string;
}

export default function ETACountdown({ etaMinutes, acceptedAt }: Props) {
  const [countdown, setCountdown] = useState(getETACountdown(etaMinutes, acceptedAt));

  useEffect(() => {
    const interval = setInterval(() => {
      setCountdown(getETACountdown(etaMinutes, acceptedAt));
    }, 30000);
    return () => clearInterval(interval);
  }, [etaMinutes, acceptedAt]);

  const colorClass = {
    green: 'text-green-600 bg-green-50',
    yellow: 'text-yellow-600 bg-yellow-50',
    red: 'text-red-600 bg-red-50',
  }[countdown.color];

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium ${colorClass} ${countdown.pulsing ? 'animate-pulse' : ''}`}>
      <Clock size={12} />
      ETA: {countdown.text}
    </span>
  );
}
