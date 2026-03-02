import apiClient from './client';
import type { PMTemplate, PMSchedule } from '@/types/api';

export const pmApi = {
  listTemplates: (params?: Record<string, unknown>) =>
    apiClient.get<PMTemplate[]>('/pm-templates', { params }),
  getTemplate: (id: string) => apiClient.get<PMTemplate>(`/pm-templates/${id}`),
  createTemplate: (data: Partial<PMTemplate>) => apiClient.post<PMTemplate>('/pm-templates', data),
  updateTemplate: (id: string, data: Partial<PMTemplate>) =>
    apiClient.patch<PMTemplate>(`/pm-templates/${id}`, data),
  deleteTemplate: (id: string) => apiClient.delete(`/pm-templates/${id}`),

  listSchedules: (params?: Record<string, unknown>) =>
    apiClient.get<PMSchedule[]>('/pm-schedules', { params }),
  skipSchedule: (id: string, reason: string) =>
    apiClient.post(`/pm-schedules/${id}/skip`, { skip_reason: reason }),
  generateNow: (id: string) =>
    apiClient.post(`/pm-schedules/${id}/generate-now`),
};
