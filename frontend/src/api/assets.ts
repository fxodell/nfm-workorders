import apiClient from './client';
import type { Asset, WorkOrderListResponse } from '@/types/api';

export const assetsApi = {
  list: (params?: { site_id?: string }) =>
    apiClient.get<Asset[]>('/assets', { params }),
  get: (id: string) => apiClient.get<Asset>(`/assets/${id}`),
  create: (data: Partial<Asset>) => apiClient.post<Asset>('/assets', data),
  update: (id: string, data: Partial<Asset>) => apiClient.patch<Asset>(`/assets/${id}`, data),
  delete: (id: string) => apiClient.delete(`/assets/${id}`),
  getWorkOrderHistory: (id: string, params?: Record<string, unknown>) =>
    apiClient.get<WorkOrderListResponse>(`/assets/${id}/work-order-history`, { params }),
  getQrCode: (id: string) =>
    apiClient.get(`/assets/${id}/qr-code`, { responseType: 'blob' }),
};
