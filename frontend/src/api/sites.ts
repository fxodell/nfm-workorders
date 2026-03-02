import apiClient from './client';
import type { Site, Asset, WorkOrderListResponse } from '@/types/api';

export const sitesApi = {
  list: (params?: { location_id?: string; area_id?: string }) =>
    apiClient.get<Site[]>('/sites', { params }),
  get: (id: string) => apiClient.get<Site>(`/sites/${id}`),
  create: (data: Partial<Site>) => apiClient.post<Site>('/sites', data),
  update: (id: string, data: Partial<Site>) => apiClient.patch<Site>(`/sites/${id}`, data),
  delete: (id: string) => apiClient.delete(`/sites/${id}`),
  getAssets: (id: string) => apiClient.get<Asset[]>(`/sites/${id}/assets`),
  getWorkOrderHistory: (id: string, params?: Record<string, unknown>) =>
    apiClient.get<WorkOrderListResponse>(`/sites/${id}/work-order-history`, { params }),
  getQrCode: (id: string) =>
    apiClient.get(`/sites/${id}/qr-code`, { responseType: 'blob' }),
};
