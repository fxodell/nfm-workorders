import { useNavigate } from 'react-router-dom';
import { MapPin, Wrench, User, Calendar } from 'lucide-react';
import type { WorkOrder } from '@/types/api';
import { WorkOrderPriority, WorkOrderStatus } from '@/types/enums';
import { getPriorityConfig } from '@/utils/priority';
import { timeAgo } from '@/utils/dateFormat';
import PriorityBadge from '@/components/PriorityBadge';
import StatusBadge from '@/components/StatusBadge';
import TypeBadge from '@/components/TypeBadge';
import SafetyFlagBadge from '@/components/SafetyFlagBadge';
import WaitingStateBadge from '@/components/WaitingStateBadge';
import SLACountdown from '@/components/SLACountdown';
import HumanReadableNumber from '@/components/HumanReadableNumber';

interface Props {
  workOrder: WorkOrder;
}

const borderColorMap: Record<WorkOrderPriority, string> = {
  [WorkOrderPriority.IMMEDIATE]: 'border-l-red-600',
  [WorkOrderPriority.URGENT]: 'border-l-orange-600',
  [WorkOrderPriority.SCHEDULED]: 'border-l-yellow-500',
  [WorkOrderPriority.DEFERRED]: 'border-l-gray-400',
};

export default function WorkOrderCard({ workOrder }: Props) {
  const navigate = useNavigate();
  const priorityConfig = getPriorityConfig(workOrder.priority);
  const borderClass = borderColorMap[workOrder.priority] || 'border-l-gray-400';

  const isWaiting =
    workOrder.status === WorkOrderStatus.WAITING_ON_OPS ||
    workOrder.status === WorkOrderStatus.WAITING_ON_PARTS;

  const handleClick = () => {
    navigate(`/work-orders/${workOrder.id}`);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleClick();
    }
  };

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      className={`
        bg-white rounded-lg shadow-sm border border-gray-200 border-l-4 ${borderClass}
        hover:shadow-md active:bg-gray-50 transition-all cursor-pointer
        min-h-[48px] p-4 select-none
      `}
      aria-label={`Work order ${workOrder.human_readable_number}, ${priorityConfig.label} priority, ${workOrder.title}`}
    >
      {/* Top row: WO number + Safety flag */}
      <div className="flex items-center justify-between gap-2 mb-2">
        <div
          className="flex items-center gap-2 min-w-0"
          onClick={(e) => e.stopPropagation()}
        >
          <HumanReadableNumber number={workOrder.human_readable_number} size="sm" />
        </div>
        {workOrder.safety_flag && (
          <SafetyFlagBadge safetyNotes={workOrder.safety_notes} size="sm" />
        )}
      </div>

      {/* Title */}
      <h3 className="text-sm font-semibold text-gray-900 mb-2 line-clamp-1">
        {workOrder.title}
      </h3>

      {/* Badges row */}
      <div className="flex flex-wrap items-center gap-1.5 mb-3">
        <PriorityBadge priority={workOrder.priority} size="sm" />
        <StatusBadge status={workOrder.status} size="sm" />
        <TypeBadge type={workOrder.type} />
        {isWaiting && <WaitingStateBadge status={workOrder.status} />}
      </div>

      {/* Description */}
      {workOrder.description && (
        <p className="text-xs text-gray-500 line-clamp-2 mb-3">
          {workOrder.description}
        </p>
      )}

      {/* Info rows */}
      <div className="space-y-1.5 text-xs text-gray-600">
        {workOrder.site_name && (
          <div className="flex items-center gap-1.5">
            <MapPin size={12} className="text-gray-400 shrink-0" />
            <span className="truncate">
              {workOrder.site_name}
              {workOrder.asset_name && (
                <span className="text-gray-400"> / {workOrder.asset_name}</span>
              )}
            </span>
          </div>
        )}

        {workOrder.assignee_name && (
          <div className="flex items-center gap-1.5">
            <User size={12} className="text-gray-400 shrink-0" />
            <span className="truncate">{workOrder.assignee_name}</span>
          </div>
        )}

        <div className="flex items-center gap-1.5">
          <Calendar size={12} className="text-gray-400 shrink-0" />
          <span>{timeAgo(workOrder.created_at)}</span>
        </div>
      </div>

      {/* SLA Countdowns */}
      {(workOrder.ack_deadline || workOrder.due_at) && (
        <div className="mt-3 pt-2 border-t border-gray-100 space-y-1">
          {workOrder.ack_deadline &&
            workOrder.status !== WorkOrderStatus.CLOSED &&
            workOrder.status !== WorkOrderStatus.VERIFIED && (
              <SLACountdown deadline={workOrder.ack_deadline} label="Ack" />
            )}
          {workOrder.due_at &&
            workOrder.status !== WorkOrderStatus.CLOSED &&
            workOrder.status !== WorkOrderStatus.VERIFIED && (
              <SLACountdown deadline={workOrder.due_at} label="Due" />
            )}
        </div>
      )}
    </div>
  );
}
