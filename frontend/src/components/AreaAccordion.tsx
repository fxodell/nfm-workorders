import { useState } from 'react';
import { ChevronDown, ChevronRight, AlertTriangle, ArrowUpCircle } from 'lucide-react';
import type { AreaDashboard } from '@/types/api';
import { WorkOrderPriority } from '@/types/enums';
import SiteCard from '@/components/SiteCard';

interface Props {
  area: AreaDashboard;
  defaultExpanded?: boolean;
}

const priorityOrder: WorkOrderPriority[] = [
  WorkOrderPriority.IMMEDIATE,
  WorkOrderPriority.URGENT,
  WorkOrderPriority.SCHEDULED,
  WorkOrderPriority.DEFERRED,
];

const priorityBadgeColors: Record<WorkOrderPriority, string> = {
  [WorkOrderPriority.IMMEDIATE]: 'bg-red-600 text-white',
  [WorkOrderPriority.URGENT]: 'bg-orange-600 text-white',
  [WorkOrderPriority.SCHEDULED]: 'bg-yellow-500 text-white',
  [WorkOrderPriority.DEFERRED]: 'bg-gray-400 text-white',
};

const priorityLabels: Record<WorkOrderPriority, string> = {
  [WorkOrderPriority.IMMEDIATE]: 'IMM',
  [WorkOrderPriority.URGENT]: 'URG',
  [WorkOrderPriority.SCHEDULED]: 'SCH',
  [WorkOrderPriority.DEFERRED]: 'DEF',
};

export default function AreaAccordion({ area, defaultExpanded = false }: Props) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  const totalOpenWOs = Object.values(area.priority_counts).reduce(
    (sum, count) => sum + count,
    0
  );

  const hasEscalations = area.escalated_count > 0;
  const hasSafetyFlags = area.safety_flag_count > 0;

  // Determine urgency color for header
  let headerAccentClass = 'border-l-gray-300';
  if (hasEscalations) {
    headerAccentClass = 'border-l-red-600';
  } else if (area.priority_counts[WorkOrderPriority.IMMEDIATE] > 0) {
    headerAccentClass = 'border-l-red-500';
  } else if (area.priority_counts[WorkOrderPriority.URGENT] > 0) {
    headerAccentClass = 'border-l-orange-500';
  } else if (totalOpenWOs > 0) {
    headerAccentClass = 'border-l-yellow-400';
  }

  return (
    <div className={`bg-white rounded-lg shadow-sm border border-gray-200 border-l-4 ${headerAccentClass} overflow-hidden`}>
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className={`
          w-full flex items-center justify-between gap-3 p-4 min-h-[48px]
          text-left hover:bg-gray-50 active:bg-gray-100 transition-colors
          ${hasEscalations ? 'bg-red-50' : ''}
        `}
        aria-expanded={expanded}
        aria-controls={`area-content-${area.area_id}`}
      >
        <div className="flex items-center gap-3 min-w-0 flex-1">
          {expanded ? (
            <ChevronDown size={20} className="text-gray-500 shrink-0" />
          ) : (
            <ChevronRight size={20} className="text-gray-500 shrink-0" />
          )}

          <h2 className="text-base font-semibold text-gray-900 truncate">
            {area.area_name}
          </h2>
        </div>

        {/* Summary badges */}
        <div className="flex items-center gap-2 shrink-0 flex-wrap justify-end">
          {/* Total open WO count */}
          {totalOpenWOs > 0 && (
            <span className="inline-flex items-center px-2 py-1 bg-gray-200 text-gray-800 text-xs font-semibold rounded-full">
              {totalOpenWOs}
            </span>
          )}

          {/* Priority count badges */}
          {priorityOrder.map((priority) => {
            const count = area.priority_counts[priority] || 0;
            if (count === 0) return null;
            return (
              <span
                key={priority}
                className={`inline-flex items-center px-2 py-0.5 text-xs font-bold rounded-full ${priorityBadgeColors[priority]}`}
                title={`${count} ${priority.toLowerCase()}`}
              >
                {priorityLabels[priority]} {count}
              </span>
            );
          })}

          {/* Escalation badge */}
          {hasEscalations && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-red-600 text-white text-xs font-bold rounded-full animate-pulse">
              <ArrowUpCircle size={12} />
              {area.escalated_count}
            </span>
          )}

          {/* Safety flag badge */}
          {hasSafetyFlags && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-yellow-400 text-yellow-900 text-xs font-bold rounded-full">
              <AlertTriangle size={12} />
              {area.safety_flag_count}
            </span>
          )}
        </div>
      </button>

      {/* Expandable content */}
      {expanded && (
        <div
          id={`area-content-${area.area_id}`}
          className="border-t border-gray-200 bg-gray-50 p-4"
        >
          {area.sites.length === 0 ? (
            <p className="text-sm text-gray-500 text-center py-4">
              No sites in this area.
            </p>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {area.sites.map((site) => (
                <SiteCard key={site.site_id} site={site} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
