import apiClient from './client';
import type { Part, PartTransaction } from '@/types/api';

export const partsApi = {
  list: (params?: { search?: string; low_stock_only?: boolean }) =>
    apiClient.get<Part[]>('/parts', { params }),
  get: (id: string) => apiClient.get<Part>(`/parts/${id}`),
  create: (data: Partial<Part>) => apiClient.post<Part>('/parts', data),
  update: (id: string, data: Partial<Part>) => apiClient.patch<Part>(`/parts/${id}`, data),
  delete: (id: string) => apiClient.delete(`/parts/${id}`),
  getTransactions: (id: string) => apiClient.get<PartTransaction[]>(`/parts/${id}/transactions`),
  createTransaction: (id: string, data: Partial<PartTransaction>) =>
    apiClient.post<PartTransaction>(`/parts/${id}/transactions`, data),
  getQrCode: (id: string) =>
    apiClient.get(`/parts/${id}/qr-code`, { responseType: 'blob' }),
};
