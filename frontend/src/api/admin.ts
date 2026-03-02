import apiClient from './client';
import type { Organization, OrgConfig, AuditLog, User, Area, Location, ShiftSchedule, OnCallSchedule, IncentiveProgram } from '@/types/api';

export const adminApi = {
  getOrg: () => apiClient.get<Organization>('/admin/org'),
  updateOrg: (data: Partial<Organization>) => apiClient.patch<Organization>('/admin/org', data),
  getOrgConfig: () => apiClient.get<OrgConfig>('/admin/org/config'),
  updateOrgConfig: (config: OrgConfig) => apiClient.put('/admin/org/config', config),
  getAuditLog: (params?: Record<string, unknown>) =>
    apiClient.get<{ items: AuditLog[]; total: number }>('/admin/audit-log', { params }),
};
