import { WorkOrderStatus } from '@/types/enums';
import { getStatusConfig } from '@/utils/status';

interface Props {
  status: WorkOrderStatus;
  size?: 'sm' | 'md';
}

export default function StatusBadge({ status, size = 'sm' }: Props) {
  const config = getStatusConfig(status);
  const sizeClass = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-3 py-1 text-sm';
  const pulseClass = status === WorkOrderStatus.ESCALATED ? 'animate-pulse' : '';
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full font-semibold ${config.bgColor} ${config.textColor} ${sizeClass} ${pulseClass}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${config.dotColor}`} />
      {config.label}
    </span>
  );
}
