import apiClient from './client';
import type { Part, PartTransaction } from '@/types/api';

export const inventoryApi = {
  list: (params?: { low_stock_only?: boolean }) =>
    apiClient.get<Part[]>('/inventory', { params }),
  get: (id: string) => apiClient.get<Part>(`/inventory/${id}`),
  create: (data: Partial<Part>) => apiClient.post<Part>('/inventory', data),
  update: (id: string, data: Partial<Part>) => apiClient.patch<Part>(`/inventory/${id}`, data),
  delete: (id: string) => apiClient.delete(`/inventory/${id}`),
  getTransactions: (id: string) => apiClient.get<PartTransaction[]>(`/inventory/${id}/transactions`),
  createTransaction: (id: string, data: Partial<PartTransaction>) =>
    apiClient.post<PartTransaction>(`/inventory/${id}/transactions`, data),
};
