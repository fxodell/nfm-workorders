import { WorkOrderStatus } from '@/types/enums';

export const statusConfig: Record<WorkOrderStatus, {
  label: string;
  variant: string;
  bgColor: string;
  textColor: string;
  dotColor: string;
}> = {
  [WorkOrderStatus.NEW]: {
    label: 'New', variant: 'default',
    bgColor: 'bg-gray-100', textColor: 'text-gray-700', dotColor: 'bg-gray-500',
  },
  [WorkOrderStatus.ASSIGNED]: {
    label: 'Assigned', variant: 'blue',
    bgColor: 'bg-blue-100', textColor: 'text-blue-700', dotColor: 'bg-blue-500',
  },
  [WorkOrderStatus.ACCEPTED]: {
    label: 'Accepted', variant: 'indigo',
    bgColor: 'bg-indigo-100', textColor: 'text-indigo-700', dotColor: 'bg-indigo-500',
  },
  [WorkOrderStatus.IN_PROGRESS]: {
    label: 'In Progress', variant: 'purple',
    bgColor: 'bg-purple-100', textColor: 'text-purple-700', dotColor: 'bg-purple-500',
  },
  [WorkOrderStatus.WAITING_ON_OPS]: {
    label: 'Waiting on Ops', variant: 'amber',
    bgColor: 'bg-amber-100', textColor: 'text-amber-700', dotColor: 'bg-amber-500',
  },
  [WorkOrderStatus.WAITING_ON_PARTS]: {
    label: 'Waiting on Parts', variant: 'amber',
    bgColor: 'bg-amber-100', textColor: 'text-amber-700', dotColor: 'bg-amber-500',
  },
  [WorkOrderStatus.RESOLVED]: {
    label: 'Resolved', variant: 'green',
    bgColor: 'bg-green-100', textColor: 'text-green-700', dotColor: 'bg-green-500',
  },
  [WorkOrderStatus.VERIFIED]: {
    label: 'Verified', variant: 'teal',
    bgColor: 'bg-teal-100', textColor: 'text-teal-700', dotColor: 'bg-teal-500',
  },
  [WorkOrderStatus.CLOSED]: {
    label: 'Closed', variant: 'dark',
    bgColor: 'bg-gray-800', textColor: 'text-gray-100', dotColor: 'bg-gray-900',
  },
  [WorkOrderStatus.ESCALATED]: {
    label: 'Escalated', variant: 'red',
    bgColor: 'bg-red-100', textColor: 'text-red-700', dotColor: 'bg-red-500',
  },
};

export function getStatusConfig(status: WorkOrderStatus) {
  return statusConfig[status] || statusConfig[WorkOrderStatus.NEW];
}

export function isActiveStatus(status: WorkOrderStatus): boolean {
  return ![WorkOrderStatus.RESOLVED, WorkOrderStatus.VERIFIED, WorkOrderStatus.CLOSED].includes(status);
}

export function isWaitingStatus(status: WorkOrderStatus): boolean {
  return [WorkOrderStatus.WAITING_ON_OPS, WorkOrderStatus.WAITING_ON_PARTS].includes(status);
}
