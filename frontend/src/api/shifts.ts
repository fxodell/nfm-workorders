import apiClient from './client';
import type { ShiftSchedule, OnCallSchedule } from '@/types/api';

export const shiftsApi = {
  list: (params?: { area_id?: string }) =>
    apiClient.get<ShiftSchedule[]>('/shifts', { params }),
  create: (data: Partial<ShiftSchedule>) => apiClient.post<ShiftSchedule>('/shifts', data),
  update: (id: string, data: Partial<ShiftSchedule>) =>
    apiClient.patch<ShiftSchedule>(`/shifts/${id}`, data),
  delete: (id: string) => apiClient.delete(`/shifts/${id}`),
  assignUsers: (id: string, userIds: string[]) =>
    apiClient.put(`/shifts/${id}/users`, { user_ids: userIds }),

  listOnCall: (params?: { area_id?: string; from?: string; to?: string }) =>
    apiClient.get<OnCallSchedule[]>('/on-call-schedules', { params }),
  createOnCall: (data: Partial<OnCallSchedule>) =>
    apiClient.post<OnCallSchedule>('/on-call-schedules', data),
  updateOnCall: (id: string, data: Partial<OnCallSchedule>) =>
    apiClient.patch<OnCallSchedule>(`/on-call-schedules/${id}`, data),
  deleteOnCall: (id: string) => apiClient.delete(`/on-call-schedules/${id}`),
};
