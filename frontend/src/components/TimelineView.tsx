import {
  ArrowRight, MessageSquare, Paperclip, Package, Timer,
  StickyNote, UserPlus, AlertCircle, ArrowUpCircle, MapPin,
  ShieldAlert,
} from 'lucide-react';
import type { TimelineEvent } from '@/types/api';
import { TimelineEventType } from '@/types/enums';
import { formatDateTime, timeAgo } from '@/utils/dateFormat';

interface Props {
  events: TimelineEvent[];
}

interface EventConfig {
  icon: React.ElementType;
  bgColor: string;
  iconColor: string;
  label: string;
}

const eventConfigs: Record<TimelineEventType, EventConfig> = {
  [TimelineEventType.STATUS_CHANGE]: {
    icon: ArrowRight,
    bgColor: 'bg-blue-100',
    iconColor: 'text-blue-600',
    label: 'Status Change',
  },
  [TimelineEventType.MESSAGE]: {
    icon: MessageSquare,
    bgColor: 'bg-green-100',
    iconColor: 'text-green-600',
    label: 'Message',
  },
  [TimelineEventType.ATTACHMENT]: {
    icon: Paperclip,
    bgColor: 'bg-purple-100',
    iconColor: 'text-purple-600',
    label: 'Attachment',
  },
  [TimelineEventType.PARTS_ADDED]: {
    icon: Package,
    bgColor: 'bg-orange-100',
    iconColor: 'text-orange-600',
    label: 'Parts Added',
  },
  [TimelineEventType.LABOR_LOGGED]: {
    icon: Timer,
    bgColor: 'bg-indigo-100',
    iconColor: 'text-indigo-600',
    label: 'Labor Logged',
  },
  [TimelineEventType.NOTE]: {
    icon: StickyNote,
    bgColor: 'bg-gray-100',
    iconColor: 'text-gray-600',
    label: 'Note',
  },
  [TimelineEventType.ASSIGNMENT_CHANGE]: {
    icon: UserPlus,
    bgColor: 'bg-cyan-100',
    iconColor: 'text-cyan-600',
    label: 'Assignment',
  },
  [TimelineEventType.SLA_BREACH]: {
    icon: AlertCircle,
    bgColor: 'bg-red-100',
    iconColor: 'text-red-600',
    label: 'SLA Breach',
  },
  [TimelineEventType.ESCALATION]: {
    icon: ArrowUpCircle,
    bgColor: 'bg-red-100',
    iconColor: 'text-red-600',
    label: 'Escalation',
  },
  [TimelineEventType.GPS_SNAPSHOT]: {
    icon: MapPin,
    bgColor: 'bg-teal-100',
    iconColor: 'text-teal-600',
    label: 'GPS Snapshot',
  },
  [TimelineEventType.SAFETY_FLAG_SET]: {
    icon: ShieldAlert,
    bgColor: 'bg-yellow-100',
    iconColor: 'text-yellow-700',
    label: 'Safety Flag',
  },
};

function getEventDescription(event: TimelineEvent): string {
  const payload = event.payload || {};

  switch (event.event_type) {
    case TimelineEventType.STATUS_CHANGE: {
      const from = (payload.from_status as string) || '';
      const to = (payload.to_status as string) || '';
      if (from && to) return `Status changed from ${from.replace(/_/g, ' ')} to ${to.replace(/_/g, ' ')}`;
      if (to) return `Status set to ${to.replace(/_/g, ' ')}`;
      return 'Status updated';
    }
    case TimelineEventType.MESSAGE:
      return (payload.content as string) || 'Sent a message';
    case TimelineEventType.ATTACHMENT:
      return `Uploaded ${(payload.filename as string) || 'a file'}`;
    case TimelineEventType.PARTS_ADDED:
      return `Added part: ${(payload.description as string) || (payload.part_number as string) || 'unknown'}`;
    case TimelineEventType.LABOR_LOGGED: {
      const minutes = payload.minutes as number;
      if (minutes) {
        const h = Math.floor(minutes / 60);
        const m = minutes % 60;
        return `Logged ${h}h ${m}m of labor`;
      }
      return 'Logged labor time';
    }
    case TimelineEventType.NOTE:
      return (payload.content as string) || 'Added a note';
    case TimelineEventType.ASSIGNMENT_CHANGE: {
      const assignee = (payload.assignee_name as string) || '';
      return assignee ? `Assigned to ${assignee}` : 'Assignment changed';
    }
    case TimelineEventType.SLA_BREACH:
      return `SLA breach: ${(payload.breach_type as string) || 'deadline exceeded'}`;
    case TimelineEventType.ESCALATION:
      return (payload.reason as string) || 'Work order escalated';
    case TimelineEventType.GPS_SNAPSHOT: {
      const lat = payload.lat as number;
      const lng = payload.lng as number;
      const stage = (payload.stage as string) || '';
      if (lat != null && lng != null) {
        return `GPS captured at ${stage}: ${lat.toFixed(6)}, ${lng.toFixed(6)}`;
      }
      return `GPS snapshot recorded${stage ? ` at ${stage}` : ''}`;
    }
    case TimelineEventType.SAFETY_FLAG_SET:
      return (payload.notes as string) || 'Safety flag toggled';
    default:
      return 'Event recorded';
  }
}

export default function TimelineView({ events }: Props) {
  if (events.length === 0) {
    return (
      <div className="p-4 text-center py-12">
        <p className="text-sm text-gray-500">No timeline events yet.</p>
      </div>
    );
  }

  return (
    <div className="p-4">
      <div className="relative">
        {/* Vertical line */}
        <div className="absolute left-5 top-0 bottom-0 w-0.5 bg-gray-200" aria-hidden="true" />

        <div className="space-y-6">
          {events.map((event, index) => {
            const config = eventConfigs[event.event_type] || {
              icon: StickyNote,
              bgColor: 'bg-gray-100',
              iconColor: 'text-gray-600',
              label: 'Event',
            };
            const Icon = config.icon;
            const description = getEventDescription(event);
            const isLast = index === events.length - 1;

            return (
              <div key={event.id} className="relative flex gap-4">
                {/* Icon circle */}
                <div
                  className={`
                    relative z-10 w-10 h-10 rounded-full flex items-center justify-center shrink-0
                    ${config.bgColor}
                  `}
                >
                  <Icon size={18} className={config.iconColor} />
                </div>

                {/* Content */}
                <div className={`flex-1 pb-2 ${!isLast ? 'min-h-[40px]' : ''}`}>
                  {/* Event type label */}
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className={`text-xs font-semibold uppercase tracking-wider ${config.iconColor}`}>
                      {config.label}
                    </span>
                  </div>

                  {/* Description */}
                  <p className="text-sm text-gray-900">{description}</p>

                  {/* GPS link for GPS_SNAPSHOT events */}
                  {event.event_type === TimelineEventType.GPS_SNAPSHOT &&
                    event.payload?.lat != null &&
                    event.payload?.lng != null && (
                      <a
                        href={`https://www.google.com/maps?q=${event.payload.lat},${event.payload.lng}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-xs text-blue-600 hover:underline mt-1"
                      >
                        <MapPin size={12} />
                        View on map
                      </a>
                    )}

                  {/* Meta info: user + timestamp */}
                  <div className="flex items-center gap-2 mt-1 text-xs text-gray-500">
                    {event.user_name && (
                      <>
                        <span className="font-medium">{event.user_name}</span>
                        <span aria-hidden="true">&middot;</span>
                      </>
                    )}
                    <span title={formatDateTime(event.created_at)}>
                      {timeAgo(event.created_at)}
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
