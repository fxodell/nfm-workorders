import apiClient from './client';

export interface ReportFilters {
  date_from?: string; date_to?: string;
  area_id?: string; format?: 'json' | 'csv';
}

export const reportsApi = {
  workOrders: (filters: ReportFilters = {}) =>
    apiClient.get('/reports/work-orders', { params: filters, responseType: filters.format === 'csv' ? 'blob' : 'json' }),
  responseTimes: (filters: ReportFilters = {}) =>
    apiClient.get('/reports/response-times', { params: filters, responseType: filters.format === 'csv' ? 'blob' : 'json' }),
  slaCompliance: (filters: ReportFilters = {}) =>
    apiClient.get('/reports/sla-compliance', { params: filters, responseType: filters.format === 'csv' ? 'blob' : 'json' }),
  partsSpend: (filters: ReportFilters = {}) =>
    apiClient.get('/reports/parts-spend', { params: filters, responseType: filters.format === 'csv' ? 'blob' : 'json' }),
  laborCost: (filters: ReportFilters = {}) =>
    apiClient.get('/reports/labor-cost', { params: filters, responseType: filters.format === 'csv' ? 'blob' : 'json' }),
  budget: (filters: ReportFilters = {}) =>
    apiClient.get('/reports/budget', { params: filters, responseType: filters.format === 'csv' ? 'blob' : 'json' }),
  pmCompletion: (filters: ReportFilters = {}) =>
    apiClient.get('/reports/pm-completion', { params: filters, responseType: filters.format === 'csv' ? 'blob' : 'json' }),
  technicianPerformance: (filters: ReportFilters = {}) =>
    apiClient.get('/reports/technician-performance', { params: filters, responseType: filters.format === 'csv' ? 'blob' : 'json' }),
  safetyFlags: (filters: ReportFilters = {}) =>
    apiClient.get('/reports/safety-flags', { params: filters, responseType: filters.format === 'csv' ? 'blob' : 'json' }),
  incentives: (filters: ReportFilters = {}) =>
    apiClient.get('/reports/incentives', { params: filters, responseType: filters.format === 'csv' ? 'blob' : 'json' }),
};
