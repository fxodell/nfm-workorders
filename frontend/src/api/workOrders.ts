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
    apiClient.get<WorkOrderListResponse>('/work-orders', { params: filters })
      .then(r => r.data),

  get: (id: string) =>
    apiClient.get<WorkOrder>(`/work-orders/${id}`)
      .then(r => r.data),

  create: (data: Partial<WorkOrder>, idempotencyKey: string) =>
    apiClient.post<WorkOrder>('/work-orders', data, {
      headers: { 'Idempotency-Key': idempotencyKey },
    }).then(r => r.data),

  update: (id: string, data: Partial<WorkOrder>, idempotencyKey?: string) =>
    apiClient.patch<WorkOrder>(`/work-orders/${id}`, data, {
      headers: idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : {},
    }).then(r => r.data),

  delete: (id: string) =>
    apiClient.delete(`/work-orders/${id}`)
      .then(r => r.data),

  assign: (id: string, assignedTo: string) =>
    apiClient.post<WorkOrder>(`/work-orders/${id}/assign`, { assigned_to: assignedTo })
      .then(r => r.data),

  accept: (id: string, etaMinutes?: number, gpsLat?: number, gpsLng?: number) =>
    apiClient.post<WorkOrder>(`/work-orders/${id}/accept`, {
      eta_minutes: etaMinutes, gps_lat: gpsLat, gps_lng: gpsLng,
    }).then(r => r.data),

  start: (id: string, gpsLat?: number, gpsLng?: number) =>
    apiClient.post<WorkOrder>(`/work-orders/${id}/start`, { gps_lat: gpsLat, gps_lng: gpsLng })
      .then(r => r.data),

  waitOps: (id: string, reason?: string) =>
    apiClient.post<WorkOrder>(`/work-orders/${id}/wait-ops`, { reason })
      .then(r => r.data),

  waitParts: (id: string, reason?: string) =>
    apiClient.post<WorkOrder>(`/work-orders/${id}/wait-parts`, { reason })
      .then(r => r.data),

  resume: (id: string) =>
    apiClient.post<WorkOrder>(`/work-orders/${id}/resume`)
      .then(r => r.data),

  resolve: (id: string, summary: string, details?: string, gpsLat?: number, gpsLng?: number) =>
    apiClient.post<WorkOrder>(`/work-orders/${id}/resolve`, {
      resolution_summary: summary, resolution_details: details,
      gps_lat: gpsLat, gps_lng: gpsLng,
    }).then(r => r.data),

  verify: (id: string) =>
    apiClient.post<WorkOrder>(`/work-orders/${id}/verify`)
      .then(r => r.data),

  close: (id: string) =>
    apiClient.post<WorkOrder>(`/work-orders/${id}/close`)
      .then(r => r.data),

  reopen: (id: string, reason: string) =>
    apiClient.post<WorkOrder>(`/work-orders/${id}/reopen`, { reason })
      .then(r => r.data),

  escalate: (id: string, reason?: string) =>
    apiClient.post<WorkOrder>(`/work-orders/${id}/escalate`, { reason })
      .then(r => r.data),

  acknowledgeEscalation: (id: string) =>
    apiClient.post<WorkOrder>(`/work-orders/${id}/acknowledge-escalation`)
      .then(r => r.data),

  // Transition dispatcher — maps action strings to the correct API method
  transition: (id: string, action: string, body?: Record<string, unknown>) => {
    switch (action) {
      case 'ASSIGN':
        return workOrderApi.assign(id, body?.assigned_to as string);
      case 'ACCEPT':
        return workOrderApi.accept(id, body?.eta_minutes as number | undefined);
      case 'START_WORK':
        return workOrderApi.start(id, body?.gps_lat as number | undefined, body?.gps_lng as number | undefined);
      case 'WAIT_ON_OPS':
        return workOrderApi.waitOps(id, body?.reason as string | undefined);
      case 'WAIT_ON_PARTS':
        return workOrderApi.waitParts(id, body?.reason as string | undefined);
      case 'RESUME':
        return workOrderApi.resume(id);
      case 'RESOLVE':
        return workOrderApi.resolve(
          id,
          body?.resolution_summary as string,
          body?.resolution_details as string | undefined,
          body?.gps_lat as number | undefined,
          body?.gps_lng as number | undefined,
        );
      case 'VERIFY':
        return workOrderApi.verify(id);
      case 'CLOSE':
        return workOrderApi.close(id);
      case 'REOPEN':
        return workOrderApi.reopen(id, body?.reason as string);
      case 'ESCALATE':
        return workOrderApi.escalate(id, body?.reason as string | undefined);
      case 'ACKNOWLEDGE_ESCALATION':
        return workOrderApi.acknowledgeEscalation(id);
      default:
        return Promise.reject(new Error(`Unknown transition action: ${action}`));
    }
  },

  // Timeline
  getTimeline: (id: string) =>
    apiClient.get<TimelineEvent[]>(`/work-orders/${id}/timeline`)
      .then(r => r.data),

  addNote: (id: string, payload: Record<string, unknown>) =>
    apiClient.post(`/work-orders/${id}/timeline`, payload)
      .then(r => r.data),

  // Attachments
  getAttachments: (id: string) =>
    apiClient.get<Attachment[]>(`/work-orders/${id}/attachments`)
      .then(r => r.data),

  createAttachment: async (id: string, file: File) => {
    // Step 1: POST metadata to get presigned upload URL
    const { data } = await apiClient.post<{
      attachment: Attachment;
      upload_url: string;
      s3_key: string;
    }>(`/work-orders/${id}/attachments`, {
      filename: file.name,
      mime_type: file.type || 'application/octet-stream',
      size_bytes: file.size,
    });

    // Step 2: PUT file directly to S3 using presigned URL
    await fetch(data.upload_url, {
      method: 'PUT',
      body: file,
      headers: { 'Content-Type': file.type || 'application/octet-stream' },
    });

    return data.attachment;
  },

  deleteAttachment: (woId: string, attachmentId: string) =>
    apiClient.delete(`/work-orders/${woId}/attachments/${attachmentId}`)
      .then(r => r.data),

  // Parts
  getParts: (id: string) =>
    apiClient.get<WorkOrderPart[]>(`/work-orders/${id}/parts`)
      .then(r => r.data),

  addPart: (id: string, data: Partial<WorkOrderPart>) =>
    apiClient.post(`/work-orders/${id}/parts`, data)
      .then(r => r.data),

  removePart: (woId: string, partId: string) =>
    apiClient.delete(`/work-orders/${woId}/parts/${partId}`)
      .then(r => r.data),

  // Labor
  getLabor: (id: string) =>
    apiClient.get<LaborLog[]>(`/work-orders/${id}/labor`)
      .then(r => r.data),

  addLabor: (id: string, minutes: number, notes?: string) =>
    apiClient.post(`/work-orders/${id}/labor`, { minutes, notes })
      .then(r => r.data),

  removeLabor: (woId: string, laborId: string) =>
    apiClient.delete(`/work-orders/${woId}/labor/${laborId}`)
      .then(r => r.data),

  // Messages
  getMessages: (id: string) =>
    apiClient.get<Message[]>(`/work-orders/${id}/messages`)
      .then(r => r.data),

  sendMessage: (id: string, content: string) =>
    apiClient.post(`/work-orders/${id}/messages`, { content })
      .then(r => r.data),

  // SLA Events
  getSlaEvents: (id: string) =>
    apiClient.get<SLAEvent[]>(`/work-orders/${id}/sla-events`)
      .then(r => r.data),
};
