import { WorkOrderType } from '@/types/enums';

const typeColors: Record<WorkOrderType, string> = {
  [WorkOrderType.REACTIVE]: 'bg-red-50 text-red-700',
  [WorkOrderType.PREVENTIVE]: 'bg-blue-50 text-blue-700',
  [WorkOrderType.INSPECTION]: 'bg-cyan-50 text-cyan-700',
  [WorkOrderType.CORRECTIVE]: 'bg-orange-50 text-orange-700',
};

export default function TypeBadge({ type }: { type: WorkOrderType }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${typeColors[type] || 'bg-gray-100 text-gray-700'}`}>
      {type}
    </span>
  );
}
