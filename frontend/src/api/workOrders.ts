import apiClient from './client';
import type {
  WorkOrder, WorkOrderListResponse, TimelineEvent,
  Attachment, WorkOrderPart, LaborLog, Message, SLAEvent,
} from '@/types/api';

export interface WorkOrderFilters {
  area_id?: string; site_id?: string; asset_id?: string;
  status?: string; priority?: string; type?: string;
  assigned_to?: string; requested_by?: string;
  safety_flag?: boolean; date_from?: string; date_to?: string;
  search?: string; page?: number; per_page?: number;
}

export const workOrderApi = {
  list: (filters: WorkOrderFilters = {}) =>
    apiClient.get<WorkOrderListResponse>('/work-orders', { params: filters }),

  get: (id: string) =>
    apiClient.get<WorkOrder>(`/work-orders/${id}`),

  create: (data: Partial<WorkOrder>, idempotencyKey: string) =>
    apiClient.post<WorkOrder>('/work-orders', data, {
      headers: { 'Idempotency-Key': idempotencyKey },
    }),

  update: (id: string, data: Partial<WorkOrder>, idempotencyKey: string) =>
    apiClient.patch<WorkOrder>(`/work-orders/${id}`, data, {
      headers: { 'Idempotency-Key': idempotencyKey },
    }),

  delete: (id: string) =>
    apiClient.delete(`/work-orders/${id}`),

  assign: (id: string, assignedTo: string) =>
    apiClient.post(`/work-orders/${id}/assign`, { assigned_to: assignedTo }),

  accept: (id: string, etaMinutes?: number, gpsLat?: number, gpsLng?: number) =>
    apiClient.post(`/work-orders/${id}/accept`, {
      eta_minutes: etaMinutes, gps_lat: gpsLat, gps_lng: gpsLng,
    }),

  start: (id: string, gpsLat?: number, gpsLng?: number) =>
    apiClient.post(`/work-orders/${id}/start`, { gps_lat: gpsLat, gps_lng: gpsLng }),

  waitOps: (id: string, reason?: string) =>
    apiClient.post(`/work-orders/${id}/wait-ops`, { reason }),

  waitParts: (id: string, reason?: string) =>
    apiClient.post(`/work-orders/${id}/wait-parts`, { reason }),

  resume: (id: string) =>
    apiClient.post(`/work-orders/${id}/resume`),

  resolve: (id: string, summary: string, details?: string, gpsLat?: number, gpsLng?: number) =>
    apiClient.post(`/work-orders/${id}/resolve`, {
      resolution_summary: summary, resolution_details: details,
      gps_lat: gpsLat, gps_lng: gpsLng,
    }),

  verify: (id: string) =>
    apiClient.post(`/work-orders/${id}/verify`),

  close: (id: string) =>
    apiClient.post(`/work-orders/${id}/close`),

  reopen: (id: string, reason: string) =>
    apiClient.post(`/work-orders/${id}/reopen`, { reason }),

  escalate: (id: string, reason?: string) =>
    apiClient.post(`/work-orders/${id}/escalate`, { reason }),

  acknowledgeEscalation: (id: string) =>
    apiClient.post(`/work-orders/${id}/acknowledge-escalation`),

  // Timeline
  getTimeline: (id: string) =>
    apiClient.get<TimelineEvent[]>(`/work-orders/${id}/timeline`),

  addNote: (id: string, payload: Record<string, unknown>) =>
    apiClient.post(`/work-orders/${id}/timeline`, payload),

  // Attachments
  getAttachments: (id: string) =>
    apiClient.get<Attachment[]>(`/work-orders/${id}/attachments`),

  createAttachment: (id: string, data: FormData) =>
    apiClient.post<Attachment>(`/work-orders/${id}/attachments`, data, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),

  deleteAttachment: (woId: string, attachmentId: string) =>
    apiClient.delete(`/work-orders/${woId}/attachments/${attachmentId}`),

  // Parts
  getParts: (id: string) =>
    apiClient.get<WorkOrderPart[]>(`/work-orders/${id}/parts`),

  addPart: (id: string, data: Partial<WorkOrderPart>) =>
    apiClient.post(`/work-orders/${id}/parts`, data),

  removePart: (woId: string, partId: string) =>
    apiClient.delete(`/work-orders/${woId}/parts/${partId}`),

  // Labor
  getLabor: (id: string) =>
    apiClient.get<LaborLog[]>(`/work-orders/${id}/labor`),

  addLabor: (id: string, minutes: number, notes?: string) =>
    apiClient.post(`/work-orders/${id}/labor`, { minutes, notes }),

  removeLabor: (woId: string, laborId: string) =>
    apiClient.delete(`/work-orders/${woId}/labor/${laborId}`),

  // Messages
  getMessages: (id: string) =>
    apiClient.get<Message[]>(`/work-orders/${id}/messages`),

  sendMessage: (id: string, content: string) =>
    apiClient.post(`/work-orders/${id}/messages`, { content }),

  // SLA Events
  getSlaEvents: (id: string) =>
    apiClient.get<SLAEvent[]>(`/work-orders/${id}/sla-events`),
};
