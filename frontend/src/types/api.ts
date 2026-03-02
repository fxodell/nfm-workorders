import {
  UserRole, WorkOrderStatus, WorkOrderPriority, WorkOrderType,
  SiteType, Permission, TimelineEventType, SLAEventType,
  TransactionType, RecurrenceType, OnCallPriority,
} from './enums';

// Auth
export interface LoginRequest { email: string; password: string; }
export interface LoginResponse {
  access_token: string; refresh_token: string; token_type: string;
  mfa_required: boolean; mfa_session_token?: string;
}
export interface TokenResponse { access_token: string; refresh_token: string; token_type: string; }
export interface MFASetupResponse { secret: string; provisioning_uri: string; qr_code_data_url: string; }
export interface WSTokenResponse { token: string; expires_in: number; }

// User
export interface User {
  id: string; org_id: string; name: string; email: string; phone?: string;
  role: UserRole; is_active: boolean; avatar_url?: string;
  mfa_enabled: boolean; email_notifications_enabled: boolean;
  last_login_at?: string; created_at: string;
}
export interface UserListResponse { items: User[]; total: number; page: number; per_page: number; }
export interface NotificationPref {
  area_id: string; push_enabled: boolean; email_enabled: boolean; on_shift: boolean;
}
export interface Certification {
  id: string; user_id: string; cert_name: string; cert_number?: string;
  issued_by?: string; issued_date?: string; expires_at?: string; notes?: string;
}

// Organization
export interface Organization {
  id: string; name: string; slug: string; logo_url?: string;
  currency_code: string; config: OrgConfig; created_at: string;
}
export interface OrgConfig {
  sla: Record<string, { ack_minutes: number; first_update_minutes: number; resolve_hours: number }>;
  escalation_enabled: boolean; closed_wo_cache_days: number;
  gps_snapshot_on_accept: boolean; gps_snapshot_on_start: boolean; gps_snapshot_on_resolve: boolean;
  timezone: string; mfa_required_roles: string[];
  default_labor_rate_per_hour: number;
}

// Area
export interface Area {
  id: string; org_id: string; name: string; description?: string;
  timezone: string; is_active: boolean; created_at: string;
}

// Location
export interface Location {
  id: string; org_id: string; area_id: string; name: string;
  address?: string; gps_lat?: number; gps_lng?: number;
  qr_code_token: string; is_active: boolean; created_at: string;
}

// Site
export interface Site {
  id: string; org_id: string; location_id: string; name: string;
  type: SiteType; address?: string; gps_lat?: number; gps_lng?: number;
  site_timezone: string; qr_code_token: string; is_active: boolean; created_at: string;
}

// Asset
export interface Asset {
  id: string; org_id: string; site_id: string; name: string;
  asset_type?: string; manufacturer?: string; model?: string;
  serial_number?: string; install_date?: string; warranty_expiry?: string;
  qr_code_token: string; notes?: string; is_active: boolean; created_at: string;
}

// Work Order
export interface WorkOrder {
  id: string; org_id: string; area_id: string; location_id: string;
  site_id: string; asset_id?: string;
  human_readable_number: string; title: string; description: string;
  type: WorkOrderType; priority: WorkOrderPriority; status: WorkOrderStatus;
  requested_by: string; assigned_to?: string; accepted_by?: string;
  verified_by?: string; closed_by?: string;
  created_at: string; updated_at: string; assigned_at?: string;
  accepted_at?: string; in_progress_at?: string; resolved_at?: string;
  verified_at?: string; closed_at?: string; escalated_at?: string;
  ack_deadline?: string; first_update_deadline?: string; due_at?: string;
  eta_minutes?: number;
  resolution_summary?: string; resolution_details?: string;
  safety_flag: boolean; safety_notes?: string; required_cert?: string;
  gps_lat_accept?: number; gps_lng_accept?: number;
  gps_lat_start?: number; gps_lng_start?: number;
  gps_lat_resolve?: number; gps_lng_resolve?: number;
  tags?: string[]; custom_fields?: Record<string, unknown>;
  // Joined fields
  site_name?: string; area_name?: string; asset_name?: string;
  requester_name?: string; assignee_name?: string;
}
export interface WorkOrderListResponse { items: WorkOrder[]; total: number; page: number; per_page: number; }

export interface TimelineEvent {
  id: string; work_order_id: string; user_id?: string;
  event_type: TimelineEventType; payload: Record<string, unknown>;
  created_at: string; user_name?: string;
}

export interface Attachment {
  id: string; work_order_id: string; uploaded_by: string;
  filename: string; mime_type?: string; size_bytes?: number;
  caption?: string; created_at: string; download_url?: string;
}

export interface WorkOrderPart {
  id: string; work_order_id: string; part_id?: string;
  part_number?: string; description?: string;
  quantity: number; unit_cost?: number;
}

export interface LaborLog {
  id: string; work_order_id: string; user_id: string;
  minutes: number; notes?: string; logged_at: string; user_name?: string;
}

export interface Message {
  id: string; work_order_id: string; user_id: string;
  sender_name: string; content: string; created_at: string;
}

export interface SLAEvent {
  id: string; work_order_id: string; event_type: SLAEventType;
  triggered_at: string; acknowledged_by?: string; acknowledged_at?: string;
}

// Parts
export interface Part {
  id: string; org_id: string; part_number: string; description?: string;
  unit_cost?: number; barcode_value?: string; supplier_name?: string;
  supplier_part_number?: string; stock_quantity: number;
  reorder_threshold: number; storage_location?: string;
  qr_code_token: string; is_active: boolean; created_at: string;
}
export interface PartTransaction {
  id: string; part_id: string; work_order_id?: string;
  transaction_type: TransactionType; quantity: number;
  notes?: string; created_by: string; created_at: string;
}

// PM
export interface PMTemplate {
  id: string; org_id: string; asset_id?: string; site_id?: string;
  title: string; description?: string; priority: WorkOrderPriority;
  checklist_json: string[]; recurrence_type: RecurrenceType;
  recurrence_interval: number; required_cert?: string;
  assigned_to_role: string; is_active: boolean; created_at: string;
}
export interface PMSchedule {
  id: string; pm_template_id: string; due_date: string;
  generated_work_order_id?: string; status: string; skip_reason?: string;
}

// Budget
export interface AreaBudget {
  id: string; area_id: string; year: number; month: number;
  budget_amount: number; actual_spend: number;
}

// Incentive
export interface IncentiveProgram {
  id: string; name: string; metric: string; target_value: number;
  bonus_description: string; period_type: string; is_active: boolean;
}
export interface UserIncentiveScore {
  id: string; user_id: string; program_id: string; period_label: string;
  score: number; achieved: boolean; calculated_at: string;
}

// Shift
export interface ShiftSchedule {
  id: string; area_id: string; name: string;
  start_time: string; end_time: string;
  days_of_week: number[]; timezone: string; is_active: boolean;
}

// On-Call
export interface OnCallSchedule {
  id: string; area_id: string; user_id: string;
  start_dt: string; end_dt: string; priority: OnCallPriority;
}

// Audit
export interface AuditLog {
  id: string; actor_user_id: string; action: string;
  entity_type: string; entity_id: string;
  old_value?: Record<string, unknown>; new_value?: Record<string, unknown>;
  created_at: string;
}

// Dashboard
export interface DashboardOverview { areas: AreaDashboard[]; }
export interface AreaDashboard {
  area_id: string; area_name: string;
  priority_counts: Record<string, number>;
  escalated_count: number; safety_flag_count: number;
  sites: SiteDashboard[];
}
export interface SiteDashboard {
  site_id: string; site_name: string; site_type: SiteType;
  highest_priority?: WorkOrderPriority; wo_count: number;
  escalated: boolean; safety_flag: boolean;
  waiting_on_ops: number; waiting_on_parts: number;
  assigned_techs: { id: string; name: string; avatar_url?: string }[];
}

// Scan
export interface ScanResponse {
  id: string; name: string; parent_id?: string;
  open_wo_count: number; safety_flag_count?: number;
}

// WebSocket events
export interface WSEvent {
  event: string; org_id: string; area_id: string;
  timestamp: string; data: Record<string, unknown>;
}

// Offline queue
export interface OfflineQueueEntry {
  id: string; type: string; payload: Record<string, unknown>;
  endpoint: string; method: string; created_at: string;
  retry_count: number; status: 'PENDING' | 'SYNCING' | 'FAILED';
}

// Pagination
export interface PaginatedResponse<T> { items: T[]; total: number; page: number; per_page: number; }
