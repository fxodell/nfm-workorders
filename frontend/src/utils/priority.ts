import { WorkOrderPriority } from '@/types/enums';

export const priorityConfig: Record<WorkOrderPriority, {
  label: string;
  color: string;
  bgColor: string;
  borderColor: string;
  textColor: string;
  description: string;
  cssClass: string;
}> = {
  [WorkOrderPriority.IMMEDIATE]: {
    label: 'Immediate',
    color: '#dc2626',
    bgColor: 'bg-red-600',
    borderColor: 'border-red-600',
    textColor: 'text-white',
    description: 'Stop everything. Safety or production at risk.',
    cssClass: 'bg-red-600 text-white animate-pulse-border border-2 border-red-600',
  },
  [WorkOrderPriority.URGENT]: {
    label: 'Urgent',
    color: '#ea580c',
    bgColor: 'bg-orange-600',
    borderColor: 'border-orange-600',
    textColor: 'text-white',
    description: 'Needs attention before end of current shift.',
    cssClass: 'bg-orange-600 text-white border-2 border-orange-600',
  },
  [WorkOrderPriority.SCHEDULED]: {
    label: 'Scheduled',
    color: '#ca8a04',
    bgColor: 'bg-yellow-600',
    borderColor: 'border-yellow-600',
    textColor: 'text-white',
    description: 'Can be planned into the next work cycle.',
    cssClass: 'bg-yellow-600 text-white border-2 border-yellow-600',
  },
  [WorkOrderPriority.DEFERRED]: {
    label: 'Deferred',
    color: '#6b7280',
    bgColor: 'bg-gray-500',
    borderColor: 'border-gray-500',
    textColor: 'text-white',
    description: 'Low priority. Do when resources allow.',
    cssClass: 'bg-gray-500 text-white border-2 border-gray-500',
  },
};

export function getPriorityConfig(priority: WorkOrderPriority) {
  return priorityConfig[priority] || priorityConfig[WorkOrderPriority.DEFERRED];
}

export function getPriorityBannerClass(priority: WorkOrderPriority, escalated: boolean): string {
  const base = priorityConfig[priority]?.bgColor || 'bg-gray-500';
  if (escalated) return `${base} animate-flash-red`;
  return base;
}
