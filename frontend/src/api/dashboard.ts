import apiClient from './client';
import type { DashboardOverview, AreaDashboard, SiteDashboard } from '@/types/api';

export const dashboardApi = {
  overview: () => apiClient.get<DashboardOverview>('/dashboard/overview'),
  area: (areaId: string) => apiClient.get<AreaDashboard>(`/dashboard/area/${areaId}`),
  site: (siteId: string) => apiClient.get<SiteDashboard>(`/dashboard/site/${siteId}`),
};
