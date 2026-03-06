import { useState, useMemo } from 'react';
import {
  AlertTriangle, MapPin, Wrench, User, Calendar, Clock, Tag,
  FileText, MessageSquare, Package, Timer, Paperclip, ChevronRight,
  Play, Pause, CheckCircle, XCircle, ArrowUpCircle, ShieldAlert,
  UserPlus, RotateCcw, Eye,
} from 'lucide-react';
import type {
  WorkOrder, TimelineEvent, Message, WorkOrderPart, LaborLog, Attachment,
} from '@/types/api';
import { WorkOrderStatus, WorkOrderPriority, UserRole } from '@/types/enums';
import { getPriorityConfig } from '@/utils/priority';
import { getStatusConfig, isWaitingStatus } from '@/utils/status';
import { formatDateTime, timeAgo } from '@/utils/dateFormat';
import PriorityBadge from '@/components/PriorityBadge';
import StatusBadge from '@/components/StatusBadge';
import TypeBadge from '@/components/TypeBadge';
import SafetyFlagBadge from '@/components/SafetyFlagBadge';
import WaitingStateBadge from '@/components/WaitingStateBadge';
import SLACountdown from '@/components/SLACountdown';
import ETACountdown from '@/components/ETACountdown';
import HumanReadableNumber from '@/components/HumanReadableNumber';
import TimelineView from '@/components/TimelineView';
import MessageThread from '@/components/MessageThread';
import PartsTable from '@/components/PartsTable';
import LaborTable from '@/components/LaborTable';
import PhotoGallery from '@/components/PhotoGallery';

type TabKey = 'details' | 'timeline' | 'messages' | 'parts' | 'labor' | 'attachments';

interface Props {
  workOrder: WorkOrder;
  timelineEvents: TimelineEvent[];
  messages: Message[];
  parts: WorkOrderPart[];
  laborLogs: LaborLog[];
  attachments: Attachment[];
  currentUserId: string;
  currentUserRole: UserRole;
  onAction: (action: string, payload?: Record<string, unknown>) => void;
  onSendMessage: (content: string) => void;
  onAddPart: (part: { part_number: string; description: string; quantity: number; unit_cost: number }) => void;
  onRemovePart: (partId: string) => void;
  onAddLabor: (entry: { minutes: number; notes: string }) => void;
  onDeleteLabor: (laborId: string) => void;
  onUploadAttachment: (file: File) => void;
  onToggleSafetyFlag: () => void;
}

const tabs: { key: TabKey; label: string; icon: React.ElementType }[] = [
  { key: 'details', label: 'Details', icon: FileText },
  { key: 'timeline', label: 'Timeline', icon: Clock },
  { key: 'messages', label: 'Messages', icon: MessageSquare },
  { key: 'parts', label: 'Parts', icon: Package },
  { key: 'labor', label: 'Labor', icon: Timer },
  { key: 'attachments', label: 'Photos', icon: Paperclip },
];

interface FSMAction {
  label: string;
  action: string;
  icon: React.ElementType;
  className: string;
  roles: UserRole[];
  fromStatuses: WorkOrderStatus[];
}

const fsmActions: FSMAction[] = [
  {
    label: 'Assign',
    action: 'ASSIGN',
    icon: UserPlus,
    className: 'bg-blue-600 hover:bg-blue-700 text-white',
    roles: [UserRole.ADMIN, UserRole.SUPERVISOR, UserRole.SUPER_ADMIN],
    fromStatuses: [WorkOrderStatus.NEW],
  },
  {
    label: 'Accept',
    action: 'ACCEPT',
    icon: CheckCircle,
    className: 'bg-indigo-600 hover:bg-indigo-700 text-white',
    roles: [UserRole.TECHNICIAN, UserRole.OPERATOR, UserRole.SUPERVISOR, UserRole.ADMIN, UserRole.SUPER_ADMIN],
    fromStatuses: [WorkOrderStatus.ASSIGNED],
  },
  {
    label: 'Start Work',
    action: 'START_WORK',
    icon: Play,
    className: 'bg-purple-600 hover:bg-purple-700 text-white',
    roles: [UserRole.TECHNICIAN, UserRole.OPERATOR, UserRole.SUPERVISOR, UserRole.ADMIN, UserRole.SUPER_ADMIN],
    fromStatuses: [WorkOrderStatus.ACCEPTED],
  },
  {
    label: 'Wait on Ops',
    action: 'WAIT_ON_OPS',
    icon: Pause,
    className: 'bg-amber-500 hover:bg-amber-600 text-white',
    roles: [UserRole.TECHNICIAN, UserRole.OPERATOR, UserRole.SUPERVISOR, UserRole.ADMIN, UserRole.SUPER_ADMIN],
    fromStatuses: [WorkOrderStatus.IN_PROGRESS],
  },
  {
    label: 'Wait on Parts',
    action: 'WAIT_ON_PARTS',
    icon: Package,
    className: 'bg-amber-500 hover:bg-amber-600 text-white',
    roles: [UserRole.TECHNICIAN, UserRole.OPERATOR, UserRole.SUPERVISOR, UserRole.ADMIN, UserRole.SUPER_ADMIN],
    fromStatuses: [WorkOrderStatus.IN_PROGRESS],
  },
  {
    label: 'Resume',
    action: 'RESUME',
    icon: Play,
    className: 'bg-purple-600 hover:bg-purple-700 text-white',
    roles: [UserRole.TECHNICIAN, UserRole.OPERATOR, UserRole.SUPERVISOR, UserRole.ADMIN, UserRole.SUPER_ADMIN],
    fromStatuses: [WorkOrderStatus.WAITING_ON_OPS, WorkOrderStatus.WAITING_ON_PARTS],
  },
  {
    label: 'Resolve',
    action: 'RESOLVE',
    icon: CheckCircle,
    className: 'bg-green-600 hover:bg-green-700 text-white',
    roles: [UserRole.TECHNICIAN, UserRole.OPERATOR, UserRole.SUPERVISOR, UserRole.ADMIN, UserRole.SUPER_ADMIN],
    fromStatuses: [WorkOrderStatus.IN_PROGRESS],
  },
  {
    label: 'Verify',
    action: 'VERIFY',
    icon: Eye,
    className: 'bg-teal-600 hover:bg-teal-700 text-white',
    roles: [UserRole.SUPERVISOR, UserRole.ADMIN, UserRole.SUPER_ADMIN],
    fromStatuses: [WorkOrderStatus.RESOLVED],
  },
  {
    label: 'Close',
    action: 'CLOSE',
    icon: XCircle,
    className: 'bg-gray-700 hover:bg-gray-800 text-white',
    roles: [UserRole.SUPERVISOR, UserRole.ADMIN, UserRole.SUPER_ADMIN],
    fromStatuses: [WorkOrderStatus.VERIFIED],
  },
  {
    label: 'Reopen',
    action: 'REOPEN',
    icon: RotateCcw,
    className: 'bg-orange-500 hover:bg-orange-600 text-white',
    roles: [UserRole.SUPERVISOR, UserRole.ADMIN, UserRole.SUPER_ADMIN],
    fromStatuses: [WorkOrderStatus.RESOLVED, WorkOrderStatus.VERIFIED, WorkOrderStatus.CLOSED],
  },
  {
    label: 'Escalate',
    action: 'ESCALATE',
    icon: ArrowUpCircle,
    className: 'bg-red-600 hover:bg-red-700 text-white',
    roles: [UserRole.TECHNICIAN, UserRole.OPERATOR, UserRole.SUPERVISOR, UserRole.ADMIN, UserRole.SUPER_ADMIN],
    fromStatuses: [
      WorkOrderStatus.NEW, WorkOrderStatus.ASSIGNED, WorkOrderStatus.ACCEPTED,
      WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.WAITING_ON_OPS, WorkOrderStatus.WAITING_ON_PARTS,
    ],
  },
  {
    label: 'Acknowledge',
    action: 'ACKNOWLEDGE_ESCALATION',
    icon: ShieldAlert,
    className: 'bg-red-700 hover:bg-red-800 text-white',
    roles: [UserRole.SUPERVISOR, UserRole.ADMIN, UserRole.SUPER_ADMIN],
    fromStatuses: [WorkOrderStatus.ESCALATED],
  },
];

export default function WorkOrderDetailPanel({
  workOrder,
  timelineEvents,
  messages,
  parts,
  laborLogs,
  attachments,
  currentUserId,
  currentUserRole,
  onAction,
  onSendMessage,
  onAddPart,
  onRemovePart,
  onAddLabor,
  onDeleteLabor,
  onUploadAttachment,
  onToggleSafetyFlag,
}: Props) {
  const [activeTab, setActiveTab] = useState<TabKey>('details');
  const priorityConfig = getPriorityConfig(workOrder.priority);

  const availableActions = useMemo(() => {
    return fsmActions.filter(
      (a) =>
        a.fromStatuses.includes(workOrder.status) &&
        a.roles.includes(currentUserRole)
    );
  }, [workOrder.status, currentUserRole]);

  const messageBadge = messages.length > 0 ? messages.length : undefined;
  const partsBadge = parts.length > 0 ? parts.length : undefined;
  const laborBadge = laborLogs.length > 0 ? laborLogs.length : undefined;
  const attachBadge = attachments.length > 0 ? attachments.length : undefined;

  const badgeMap: Partial<Record<TabKey, number | undefined>> = {
    messages: messageBadge,
    parts: partsBadge,
    labor: laborBadge,
    attachments: attachBadge,
  };

  return (
    <div className="flex flex-col h-full bg-white">
      {/* Safety flag banner */}
      {workOrder.safety_flag && (
        <div className="bg-yellow-400 px-4 py-3 flex items-center gap-2">
          <AlertTriangle size={20} className="text-yellow-900 shrink-0" />
          <div className="flex-1">
            <span className="font-bold text-yellow-900 text-sm">SAFETY HAZARD FLAGGED</span>
            {workOrder.safety_notes && (
              <p className="text-yellow-800 text-xs mt-0.5">{workOrder.safety_notes}</p>
            )}
          </div>
          <button
            onClick={onToggleSafetyFlag}
            className="min-h-[48px] min-w-[48px] flex items-center justify-center px-3 py-2 bg-yellow-600 hover:bg-yellow-700 text-white text-xs font-semibold rounded"
          >
            Clear
          </button>
        </div>
      )}

      {/* Header */}
      <div className="px-4 pt-4 pb-3 border-b border-gray-200">
        <div className="flex items-start justify-between gap-2 mb-2">
          <HumanReadableNumber number={workOrder.human_readable_number} size="lg" />
          {!workOrder.safety_flag && (
            <button
              onClick={onToggleSafetyFlag}
              className="min-h-[48px] min-w-[48px] flex items-center justify-center p-2 border border-yellow-400 text-yellow-700 hover:bg-yellow-50 rounded text-xs font-medium gap-1"
              title="Flag safety hazard"
            >
              <AlertTriangle size={16} />
              Flag
            </button>
          )}
        </div>

        <h1 className="text-lg font-bold text-gray-900 mb-2">{workOrder.title}</h1>

        <div className="flex flex-wrap items-center gap-1.5 mb-3">
          <PriorityBadge priority={workOrder.priority} size="md" />
          <StatusBadge status={workOrder.status} size="md" />
          <TypeBadge type={workOrder.type} />
          {isWaitingStatus(workOrder.status) && (
            <WaitingStateBadge status={workOrder.status} />
          )}
        </div>

        {/* SLA Countdowns */}
        {(workOrder.ack_deadline || workOrder.first_update_deadline || workOrder.due_at) && (
          <div className="space-y-1 mb-2">
            {workOrder.ack_deadline && (
              <SLACountdown deadline={workOrder.ack_deadline} label="Acknowledge by" />
            )}
            {workOrder.first_update_deadline && (
              <SLACountdown deadline={workOrder.first_update_deadline} label="First update by" />
            )}
            {workOrder.due_at && (
              <SLACountdown deadline={workOrder.due_at} label="Resolve by" />
            )}
          </div>
        )}

        {workOrder.eta_minutes != null && workOrder.accepted_at && (
          <div className="mb-2">
            <ETACountdown etaMinutes={workOrder.eta_minutes} acceptedAt={workOrder.accepted_at} />
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 overflow-x-auto shrink-0">
        <div className="flex min-w-max">
          {tabs.map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              onClick={() => setActiveTab(key)}
              className={`
                flex items-center gap-1.5 px-4 py-3 min-h-[48px] text-sm font-medium
                border-b-2 transition-colors whitespace-nowrap
                ${
                  activeTab === key
                    ? 'border-navy-900 text-navy-900'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }
              `}
            >
              <Icon size={16} />
              {label}
              {badgeMap[key] != null && (
                <span className="ml-1 bg-gray-200 text-gray-700 text-xs rounded-full px-1.5 py-0.5 min-w-[20px] text-center">
                  {badgeMap[key]}
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-auto">
        {activeTab === 'details' && (
          <DetailsTab
            workOrder={workOrder}
            currentUserId={currentUserId}
            currentUserRole={currentUserRole}
          />
        )}
        {activeTab === 'timeline' && (
          <TimelineView events={timelineEvents} />
        )}
        {activeTab === 'messages' && (
          <MessageThread
            messages={messages}
            currentUserId={currentUserId}
            onSendMessage={onSendMessage}
          />
        )}
        {activeTab === 'parts' && (
          <PartsTable
            parts={parts}
            onAddPart={onAddPart}
            onRemovePart={onRemovePart}
          />
        )}
        {activeTab === 'labor' && (
          <LaborTable
            laborLogs={laborLogs}
            currentUserId={currentUserId}
            onAddLabor={onAddLabor}
            onDeleteLabor={onDeleteLabor}
          />
        )}
        {activeTab === 'attachments' && (
          <PhotoGallery
            attachments={attachments}
            onUpload={onUploadAttachment}
          />
        )}
      </div>

      {/* Action Buttons */}
      {availableActions.length > 0 && (
        <div className="border-t border-gray-200 bg-gray-50 p-3 shrink-0">
          <div className="flex flex-wrap gap-2">
            {availableActions.map((act) => {
              const Icon = act.icon;
              return (
                <button
                  key={act.action}
                  onClick={() => onAction(act.action)}
                  className={`
                    inline-flex items-center gap-2 px-4 py-3 rounded-lg font-medium text-sm
                    min-h-[48px] min-w-[48px] transition-colors ${act.className}
                  `}
                >
                  <Icon size={18} />
                  {act.label}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Details Sub-Tab ────────────────────────────────────────── */

function DetailsTab({
  workOrder,
  currentUserId,
  currentUserRole,
}: {
  workOrder: WorkOrder;
  currentUserId: string;
  currentUserRole: UserRole;
}) {
  const hasSiteGps = workOrder.site_gps_lat != null && workOrder.site_gps_lng != null;
  const siteMapsUrl = hasSiteGps
    ? `https://www.google.com/maps?q=${workOrder.site_gps_lat},${workOrder.site_gps_lng}`
    : null;

  return (
    <div className="p-4 space-y-6">
      {/* Description */}
      <section>
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Description</h3>
        <p className="text-sm text-gray-800 whitespace-pre-wrap">{workOrder.description || 'No description provided.'}</p>
      </section>

      {/* Location */}
      <section>
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Location</h3>
        <div className="space-y-2 text-sm">
          {workOrder.area_name && (
            <DetailRow icon={MapPin} label="Area" value={workOrder.area_name} />
          )}
          {workOrder.site_name && (
            <DetailRow icon={MapPin} label="Site" value={workOrder.site_name} />
          )}
          {workOrder.site_address && (
            <DetailRow icon={MapPin} label="Address" value={workOrder.site_address} />
          )}
          {hasSiteGps && siteMapsUrl && (
            <div className="flex items-center gap-2">
              <MapPin size={14} className="text-gray-400 shrink-0" />
              <span className="text-gray-500 min-w-[100px]">Site GPS</span>
              <a
                href={siteMapsUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:text-blue-800 underline font-mono text-sm"
              >
                {workOrder.site_gps_lat!.toFixed(6)}, {workOrder.site_gps_lng!.toFixed(6)}
              </a>
            </div>
          )}
          {workOrder.asset_name && (
            <DetailRow icon={Wrench} label="Asset" value={workOrder.asset_name} />
          )}
        </div>
      </section>

      {/* People */}
      <section>
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">People</h3>
        <div className="space-y-2 text-sm">
          {workOrder.requester_name && (
            <DetailRow icon={User} label="Requested by" value={workOrder.requester_name} />
          )}
          {workOrder.assignee_name && (
            <DetailRow icon={User} label="Assigned to" value={workOrder.assignee_name} />
          )}
        </div>
      </section>

      {/* Key Dates */}
      <section>
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Dates</h3>
        <div className="space-y-2 text-sm">
          <DetailRow icon={Calendar} label="Created" value={formatDateTime(workOrder.created_at)} />
          {workOrder.assigned_at && (
            <DetailRow icon={Calendar} label="Assigned" value={formatDateTime(workOrder.assigned_at)} />
          )}
          {workOrder.accepted_at && (
            <DetailRow icon={Calendar} label="Accepted" value={formatDateTime(workOrder.accepted_at)} />
          )}
          {workOrder.in_progress_at && (
            <DetailRow icon={Calendar} label="Work started" value={formatDateTime(workOrder.in_progress_at)} />
          )}
          {workOrder.resolved_at && (
            <DetailRow icon={Calendar} label="Resolved" value={formatDateTime(workOrder.resolved_at)} />
          )}
          {workOrder.verified_at && (
            <DetailRow icon={Calendar} label="Verified" value={formatDateTime(workOrder.verified_at)} />
          )}
          {workOrder.closed_at && (
            <DetailRow icon={Calendar} label="Closed" value={formatDateTime(workOrder.closed_at)} />
          )}
          {workOrder.escalated_at && (
            <DetailRow icon={ArrowUpCircle} label="Escalated" value={formatDateTime(workOrder.escalated_at)} />
          )}
        </div>
      </section>

      {/* GPS Snapshots */}
      {(workOrder.gps_lat_accept != null || workOrder.gps_lat_start != null || workOrder.gps_lat_resolve != null) && (
        <section>
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">GPS Snapshots</h3>
          <div className="space-y-2 text-sm">
            {workOrder.gps_lat_accept != null && workOrder.gps_lng_accept != null && (
              <GPSRow label="Accept" lat={workOrder.gps_lat_accept} lng={workOrder.gps_lng_accept} />
            )}
            {workOrder.gps_lat_start != null && workOrder.gps_lng_start != null && (
              <GPSRow label="Start" lat={workOrder.gps_lat_start} lng={workOrder.gps_lng_start} />
            )}
            {workOrder.gps_lat_resolve != null && workOrder.gps_lng_resolve != null && (
              <GPSRow label="Resolve" lat={workOrder.gps_lat_resolve} lng={workOrder.gps_lng_resolve} />
            )}
          </div>
        </section>
      )}

      {/* Resolution */}
      {(workOrder.resolution_summary || workOrder.resolution_details) && (
        <section>
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Resolution</h3>
          {workOrder.resolution_summary && (
            <p className="text-sm font-medium text-gray-800 mb-1">{workOrder.resolution_summary}</p>
          )}
          {workOrder.resolution_details && (
            <p className="text-sm text-gray-600 whitespace-pre-wrap">{workOrder.resolution_details}</p>
          )}
        </section>
      )}

      {/* Tags */}
      {workOrder.tags && workOrder.tags.length > 0 && (
        <section>
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Tags</h3>
          <div className="flex flex-wrap gap-1.5">
            {workOrder.tags.map((tag) => (
              <span
                key={tag}
                className="inline-flex items-center gap-1 px-2 py-1 bg-gray-100 text-gray-700 text-xs rounded-full"
              >
                <Tag size={10} />
                {tag}
              </span>
            ))}
          </div>
        </section>
      )}

      {/* Required Certification */}
      {workOrder.required_cert && (
        <section>
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Required Certification</h3>
          <p className="text-sm text-gray-800">{workOrder.required_cert}</p>
        </section>
      )}
    </div>
  );
}

function DetailRow({ icon: Icon, label, value }: { icon: React.ElementType; label: string; value: string }) {
  return (
    <div className="flex items-center gap-2">
      <Icon size={14} className="text-gray-400 shrink-0" />
      <span className="text-gray-500 min-w-[100px]">{label}</span>
      <span className="text-gray-900 font-medium">{value}</span>
    </div>
  );
}

function GPSRow({ label, lat, lng }: { label: string; lat: number; lng: number }) {
  const mapsUrl = `https://www.google.com/maps?q=${lat},${lng}`;
  return (
    <div className="flex items-center gap-2">
      <MapPin size={14} className="text-gray-400 shrink-0" />
      <span className="text-gray-500 min-w-[100px]">{label}</span>
      <a
        href={mapsUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="text-blue-600 hover:underline text-sm font-mono"
      >
        {lat.toFixed(6)}, {lng.toFixed(6)}
      </a>
    </div>
  );
}
