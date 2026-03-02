import { WorkOrderPriority } from '@/types/enums';
import { getPriorityConfig } from '@/utils/priority';

interface Props {
  priority: WorkOrderPriority;
  size?: 'sm' | 'md';
}

export default function PriorityBadge({ priority, size = 'sm' }: Props) {
  const config = getPriorityConfig(priority);
  const sizeClass = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-3 py-1 text-sm';
  return (
    <span className={`inline-flex items-center rounded-full font-semibold ${config.bgColor} ${config.textColor} ${sizeClass}`}>
      {priority === WorkOrderPriority.IMMEDIATE && '🔴 '}
      {priority === WorkOrderPriority.URGENT && '🟠 '}
      {priority === WorkOrderPriority.SCHEDULED && '🟡 '}
      {priority === WorkOrderPriority.DEFERRED && '⬜ '}
      {config.label}
    </span>
  );
}
