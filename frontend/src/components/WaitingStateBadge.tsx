import { WorkOrderStatus } from '@/types/enums';
import { Pause } from 'lucide-react';

export default function WaitingStateBadge({ status }: { status: WorkOrderStatus }) {
  if (status !== WorkOrderStatus.WAITING_ON_OPS && status !== WorkOrderStatus.WAITING_ON_PARTS) return null;
  const label = status === WorkOrderStatus.WAITING_ON_OPS ? 'Waiting on Ops' : 'Waiting on Parts';
  return (
    <span className="inline-flex items-center gap-1 px-2 py-1 rounded bg-amber-100 text-amber-800 text-xs font-medium">
      <Pause size={12} /> {label}
    </span>
  );
}
