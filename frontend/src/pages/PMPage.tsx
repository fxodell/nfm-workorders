import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Calendar, ListChecks, Clock, Plus, X, ChevronLeft, ChevronRight,
  SkipForward, Play, Search, Filter, AlertTriangle, Loader2,
  Trash2, Edit2, CheckCircle2, XCircle, ToggleLeft, ToggleRight,
} from 'lucide-react';
import {
  format, startOfMonth, endOfMonth, eachDayOfInterval, isSameDay,
  addMonths, subMonths, getDay, isToday, isBefore, parseISO,
} from 'date-fns';
import { pmApi } from '@/api/pm';
import { sitesApi } from '@/api/sites';
import { assetsApi } from '@/api/assets';
import type { PMTemplate, PMSchedule, Site, Asset } from '@/types/api';
import { RecurrenceType, WorkOrderPriority } from '@/types/enums';
import PriorityBadge from '@/components/PriorityBadge';

type TabKey = 'calendar' | 'templates' | 'schedules';

const recurrenceLabels: Record<RecurrenceType, string> = {
  [RecurrenceType.DAILY]: 'Daily',
  [RecurrenceType.WEEKLY]: 'Weekly',
  [RecurrenceType.MONTHLY]: 'Monthly',
  [RecurrenceType.CUSTOM_DAYS]: 'Custom Days',
  [RecurrenceType.METER_BASED]: 'Meter Based',
};

const scheduleStatusColors: Record<string, string> = {
  PENDING: 'bg-blue-100 text-blue-800',
  OVERDUE: 'bg-red-100 text-red-800',
  GENERATED: 'bg-green-100 text-green-800',
  SKIPPED: 'bg-gray-100 text-gray-600',
};

export default function PMPage() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<TabKey>('calendar');
  const [calendarMonth, setCalendarMonth] = useState(new Date());
  const [showTemplateModal, setShowTemplateModal] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<PMTemplate | null>(null);
  const [showSkipModal, setShowSkipModal] = useState<string | null>(null);
  const [skipReason, setSkipReason] = useState('');

  // Filters
  const [filterSiteId, setFilterSiteId] = useState('');
  const [filterAssetId, setFilterAssetId] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  // Data fetching
  const { data: templates = [], isLoading: templatesLoading } = useQuery({
    queryKey: ['pm-templates', filterSiteId, filterAssetId],
    queryFn: async () => {
      const params: Record<string, unknown> = {};
      if (filterSiteId) params.site_id = filterSiteId;
      if (filterAssetId) params.asset_id = filterAssetId;
      const res = await pmApi.listTemplates(params);
      return res.data;
    },
  });

  const { data: schedules = [], isLoading: schedulesLoading } = useQuery({
    queryKey: ['pm-schedules', filterSiteId, filterAssetId, filterStatus],
    queryFn: async () => {
      const params: Record<string, unknown> = {};
      if (filterSiteId) params.site_id = filterSiteId;
      if (filterAssetId) params.asset_id = filterAssetId;
      if (filterStatus) params.status = filterStatus;
      const res = await pmApi.listSchedules(params);
      return res.data;
    },
  });

  const { data: sites = [] } = useQuery({
    queryKey: ['sites'],
    queryFn: async () => {
      const res = await sitesApi.list();
      return res.data;
    },
  });

  const { data: assets = [] } = useQuery({
    queryKey: ['assets'],
    queryFn: async () => {
      const res = await assetsApi.list();
      return res.data;
    },
  });

  // Mutations
  const toggleActiveMutation = useMutation({
    mutationFn: ({ id, isActive }: { id: string; isActive: boolean }) =>
      pmApi.updateTemplate(id, { is_active: isActive }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['pm-templates'] }),
  });

  const skipMutation = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      pmApi.skipSchedule(id, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pm-schedules'] });
      setShowSkipModal(null);
      setSkipReason('');
    },
  });

  const generateMutation = useMutation({
    mutationFn: (id: string) => pmApi.generateNow(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['pm-schedules'] }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => pmApi.deleteTemplate(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['pm-templates'] }),
  });

  // Filtered templates
  const filteredTemplates = useMemo(() => {
    if (!searchQuery) return templates;
    const q = searchQuery.toLowerCase();
    return templates.filter(
      (t) =>
        t.title.toLowerCase().includes(q) ||
        t.description?.toLowerCase().includes(q)
    );
  }, [templates, searchQuery]);

  // Calendar data
  const calendarDays = useMemo(() => {
    const start = startOfMonth(calendarMonth);
    const end = endOfMonth(calendarMonth);
    return eachDayOfInterval({ start, end });
  }, [calendarMonth]);

  const scheduleDotsByDay = useMemo(() => {
    const map = new Map<string, PMSchedule[]>();
    schedules.forEach((s) => {
      const key = format(parseISO(s.due_date), 'yyyy-MM-dd');
      const existing = map.get(key) || [];
      existing.push(s);
      map.set(key, existing);
    });
    return map;
  }, [schedules]);

  const tabs: { key: TabKey; label: string; icon: React.ElementType }[] = [
    { key: 'calendar', label: 'Calendar', icon: Calendar },
    { key: 'templates', label: 'Templates', icon: ListChecks },
    { key: 'schedules', label: 'Schedules', icon: Clock },
  ];

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Preventive Maintenance</h1>
        {activeTab === 'templates' && (
          <button
            onClick={() => {
              setEditingTemplate(null);
              setShowTemplateModal(true);
            }}
            className="flex items-center gap-2 px-4 py-2.5 bg-navy-900 text-white rounded-lg font-medium min-h-[48px] active:bg-navy-800 transition-colors"
          >
            <Plus size={18} />
            New Template
          </button>
        )}
      </div>

      {/* Tabs */}
      <div className="flex border-b border-gray-200">
        {tabs.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors min-h-[48px] ${
              activeTab === key
                ? 'border-navy-900 text-navy-900'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            <Icon size={16} />
            {label}
          </button>
        ))}
      </div>

      {/* Filters */}
      {(activeTab === 'templates' || activeTab === 'schedules') && (
        <div className="flex flex-wrap gap-3">
          {activeTab === 'templates' && (
            <div className="relative flex-1 min-w-[200px]">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                placeholder="Search templates..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-4 py-2.5 border border-gray-300 rounded-lg text-sm min-h-[48px] focus:ring-2 focus:ring-navy-500 focus:border-navy-500"
              />
            </div>
          )}
          <select
            value={filterSiteId}
            onChange={(e) => setFilterSiteId(e.target.value)}
            className="px-3 py-2.5 border border-gray-300 rounded-lg text-sm min-h-[48px] bg-white"
          >
            <option value="">All Sites</option>
            {sites.map((s: Site) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
          <select
            value={filterAssetId}
            onChange={(e) => setFilterAssetId(e.target.value)}
            className="px-3 py-2.5 border border-gray-300 rounded-lg text-sm min-h-[48px] bg-white"
          >
            <option value="">All Assets</option>
            {assets.map((a: Asset) => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </select>
          {activeTab === 'schedules' && (
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              className="px-3 py-2.5 border border-gray-300 rounded-lg text-sm min-h-[48px] bg-white"
            >
              <option value="">All Statuses</option>
              <option value="PENDING">Pending</option>
              <option value="OVERDUE">Overdue</option>
              <option value="GENERATED">Generated</option>
              <option value="SKIPPED">Skipped</option>
            </select>
          )}
        </div>
      )}

      {/* Calendar Tab */}
      {activeTab === 'calendar' && (
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          {/* Month navigation */}
          <div className="flex items-center justify-between mb-4">
            <button
              onClick={() => setCalendarMonth(subMonths(calendarMonth, 1))}
              className="p-3 hover:bg-gray-100 rounded-lg min-h-[48px] min-w-[48px] flex items-center justify-center"
              aria-label="Previous month"
            >
              <ChevronLeft size={20} />
            </button>
            <h2 className="text-lg font-semibold text-gray-900">
              {format(calendarMonth, 'MMMM yyyy')}
            </h2>
            <button
              onClick={() => setCalendarMonth(addMonths(calendarMonth, 1))}
              className="p-3 hover:bg-gray-100 rounded-lg min-h-[48px] min-w-[48px] flex items-center justify-center"
              aria-label="Next month"
            >
              <ChevronRight size={20} />
            </button>
          </div>

          {/* Day headers */}
          <div className="grid grid-cols-7 gap-1 mb-1">
            {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((day) => (
              <div key={day} className="text-center text-xs font-medium text-gray-500 py-2">
                {day}
              </div>
            ))}
          </div>

          {/* Calendar grid */}
          <div className="grid grid-cols-7 gap-1">
            {/* Leading empty cells */}
            {Array.from({ length: getDay(calendarDays[0]) }).map((_, i) => (
              <div key={`empty-${i}`} className="h-16" />
            ))}

            {calendarDays.map((day) => {
              const key = format(day, 'yyyy-MM-dd');
              const daySchedules = scheduleDotsByDay.get(key) || [];
              const hasOverdue = daySchedules.some((s) => s.status === 'OVERDUE');
              const today = isToday(day);

              return (
                <div
                  key={key}
                  className={`h-16 p-1 rounded-lg border text-sm transition-colors ${
                    today
                      ? 'border-navy-500 bg-navy-50'
                      : 'border-transparent hover:bg-gray-50'
                  }`}
                >
                  <div className={`font-medium text-xs ${today ? 'text-navy-900' : 'text-gray-700'}`}>
                    {format(day, 'd')}
                  </div>
                  {daySchedules.length > 0 && (
                    <div className="flex flex-wrap gap-0.5 mt-1">
                      {daySchedules.slice(0, 3).map((s) => (
                        <div
                          key={s.id}
                          className={`w-2 h-2 rounded-full ${
                            s.status === 'OVERDUE'
                              ? 'bg-red-500'
                              : s.status === 'GENERATED'
                              ? 'bg-green-500'
                              : s.status === 'SKIPPED'
                              ? 'bg-gray-400'
                              : 'bg-blue-500'
                          }`}
                          title={`PM ${s.status}`}
                        />
                      ))}
                      {daySchedules.length > 3 && (
                        <span className="text-[10px] text-gray-400">
                          +{daySchedules.length - 3}
                        </span>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Legend */}
          <div className="flex flex-wrap items-center gap-4 mt-4 pt-4 border-t border-gray-100 text-xs text-gray-500">
            <div className="flex items-center gap-1.5">
              <div className="w-2.5 h-2.5 rounded-full bg-blue-500" />
              Pending
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-2.5 h-2.5 rounded-full bg-red-500" />
              Overdue
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-2.5 h-2.5 rounded-full bg-green-500" />
              Generated
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-2.5 h-2.5 rounded-full bg-gray-400" />
              Skipped
            </div>
          </div>
        </div>
      )}

      {/* Templates Tab */}
      {activeTab === 'templates' && (
        <div className="space-y-3">
          {templatesLoading && (
            <div className="flex items-center justify-center py-12">
              <Loader2 size={32} className="animate-spin text-navy-600" />
            </div>
          )}

          {!templatesLoading && filteredTemplates.length === 0 && (
            <div className="text-center py-12">
              <ListChecks size={48} className="mx-auto text-gray-300 mb-3" />
              <p className="text-gray-500">No PM templates found</p>
              <button
                onClick={() => {
                  setEditingTemplate(null);
                  setShowTemplateModal(true);
                }}
                className="mt-4 text-navy-600 font-medium min-h-[48px]"
              >
                Create your first template
              </button>
            </div>
          )}

          {filteredTemplates.map((template) => (
            <div
              key={template.id}
              className="bg-white rounded-lg border border-gray-200 p-4 space-y-3"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="font-semibold text-gray-900 truncate">{template.title}</h3>
                    {!template.is_active && (
                      <span className="px-2 py-0.5 bg-gray-100 text-gray-500 text-xs rounded-full font-medium">
                        Inactive
                      </span>
                    )}
                  </div>
                  {template.description && (
                    <p className="text-sm text-gray-500 line-clamp-2">{template.description}</p>
                  )}
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  <button
                    onClick={() => {
                      setEditingTemplate(template);
                      setShowTemplateModal(true);
                    }}
                    className="p-3 hover:bg-gray-100 rounded-lg min-h-[48px] min-w-[48px] flex items-center justify-center"
                    aria-label="Edit template"
                  >
                    <Edit2 size={16} className="text-gray-600" />
                  </button>
                  <button
                    onClick={() => toggleActiveMutation.mutate({ id: template.id, isActive: !template.is_active })}
                    className="p-3 hover:bg-gray-100 rounded-lg min-h-[48px] min-w-[48px] flex items-center justify-center"
                    aria-label={template.is_active ? 'Deactivate' : 'Activate'}
                  >
                    {template.is_active ? (
                      <ToggleRight size={20} className="text-green-600" />
                    ) : (
                      <ToggleLeft size={20} className="text-gray-400" />
                    )}
                  </button>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2 text-xs">
                <PriorityBadge priority={template.priority} size="sm" />
                <span className="px-2 py-0.5 bg-purple-100 text-purple-800 rounded-full font-medium">
                  {recurrenceLabels[template.recurrence_type]} / {template.recurrence_interval}
                </span>
                {template.required_cert && (
                  <span className="px-2 py-0.5 bg-yellow-100 text-yellow-800 rounded-full font-medium">
                    Cert: {template.required_cert}
                  </span>
                )}
              </div>

              <div className="flex flex-wrap items-center gap-3 text-xs text-gray-500">
                {template.site_id && (
                  <span>Site: {sites.find((s: Site) => s.id === template.site_id)?.name || 'Unknown'}</span>
                )}
                {template.asset_id && (
                  <span>Asset: {assets.find((a: Asset) => a.id === template.asset_id)?.name || 'Unknown'}</span>
                )}
                {template.checklist_json?.length > 0 && (
                  <span>{template.checklist_json.length} checklist item{template.checklist_json.length !== 1 ? 's' : ''}</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Schedules Tab */}
      {activeTab === 'schedules' && (
        <div className="space-y-3">
          {schedulesLoading && (
            <div className="flex items-center justify-center py-12">
              <Loader2 size={32} className="animate-spin text-navy-600" />
            </div>
          )}

          {!schedulesLoading && schedules.length === 0 && (
            <div className="text-center py-12">
              <Clock size={48} className="mx-auto text-gray-300 mb-3" />
              <p className="text-gray-500">No PM schedules found</p>
            </div>
          )}

          {schedules.map((schedule) => {
            const template = templates.find((t) => t.id === schedule.pm_template_id);
            const isOverdue = schedule.status === 'OVERDUE' || (
              schedule.status === 'PENDING' && isBefore(parseISO(schedule.due_date), new Date())
            );

            return (
              <div
                key={schedule.id}
                className={`bg-white rounded-lg border p-4 ${
                  isOverdue ? 'border-red-300 bg-red-50' : 'border-gray-200'
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1 space-y-2">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="font-semibold text-gray-900">
                        {template?.title || 'Unknown Template'}
                      </h3>
                      <span className={`px-2 py-0.5 text-xs rounded-full font-medium ${
                        isOverdue
                          ? 'bg-red-100 text-red-800'
                          : scheduleStatusColors[schedule.status] || 'bg-gray-100 text-gray-600'
                      }`}>
                        {isOverdue ? 'OVERDUE' : schedule.status}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 text-sm text-gray-500">
                      <span>Due: {format(parseISO(schedule.due_date), 'MMM d, yyyy')}</span>
                      {schedule.skip_reason && (
                        <span className="text-gray-400 italic">Reason: {schedule.skip_reason}</span>
                      )}
                    </div>
                    {isOverdue && (
                      <div className="flex items-center gap-1 text-red-600 text-xs font-medium">
                        <AlertTriangle size={12} />
                        Overdue - action required
                      </div>
                    )}
                  </div>

                  {/* Schedule actions */}
                  {(schedule.status === 'PENDING' || isOverdue) && (
                    <div className="flex items-center gap-1 shrink-0">
                      <button
                        onClick={() => generateMutation.mutate(schedule.id)}
                        disabled={generateMutation.isPending}
                        className="p-3 hover:bg-green-50 rounded-lg min-h-[48px] min-w-[48px] flex items-center justify-center"
                        aria-label="Generate work order now"
                        title="Generate Now"
                      >
                        <Play size={16} className="text-green-600" />
                      </button>
                      <button
                        onClick={() => setShowSkipModal(schedule.id)}
                        className="p-3 hover:bg-orange-50 rounded-lg min-h-[48px] min-w-[48px] flex items-center justify-center"
                        aria-label="Skip this schedule"
                        title="Skip"
                      >
                        <SkipForward size={16} className="text-orange-600" />
                      </button>
                    </div>
                  )}

                  {schedule.status === 'GENERATED' && (
                    <div className="flex items-center gap-1">
                      <CheckCircle2 size={20} className="text-green-600" />
                    </div>
                  )}

                  {schedule.status === 'SKIPPED' && (
                    <div className="flex items-center gap-1">
                      <XCircle size={20} className="text-gray-400" />
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Template Create/Edit Modal */}
      {showTemplateModal && (
        <TemplateModal
          template={editingTemplate}
          sites={sites}
          assets={assets}
          onClose={() => {
            setShowTemplateModal(false);
            setEditingTemplate(null);
          }}
        />
      )}

      {/* Skip Reason Modal */}
      {showSkipModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl w-full max-w-md p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">Skip PM Schedule</h2>
              <button
                onClick={() => {
                  setShowSkipModal(null);
                  setSkipReason('');
                }}
                className="p-2 hover:bg-gray-100 rounded-lg min-h-[48px] min-w-[48px] flex items-center justify-center"
              >
                <X size={20} />
              </button>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Reason for skipping <span className="text-red-500">*</span>
              </label>
              <textarea
                value={skipReason}
                onChange={(e) => setSkipReason(e.target.value)}
                rows={3}
                placeholder="Enter reason for skipping this PM..."
                className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-navy-500 focus:border-navy-500"
              />
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => {
                  setShowSkipModal(null);
                  setSkipReason('');
                }}
                className="flex-1 px-4 py-2.5 border border-gray-300 rounded-lg font-medium text-gray-700 min-h-[48px]"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  if (showSkipModal && skipReason.trim()) {
                    skipMutation.mutate({ id: showSkipModal, reason: skipReason.trim() });
                  }
                }}
                disabled={!skipReason.trim() || skipMutation.isPending}
                className="flex-1 px-4 py-2.5 bg-orange-600 text-white rounded-lg font-medium min-h-[48px] disabled:opacity-50"
              >
                {skipMutation.isPending ? 'Skipping...' : 'Skip Schedule'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Template Create/Edit Modal ──────────────────────────────────────────────

interface TemplateModalProps {
  template: PMTemplate | null;
  sites: Site[];
  assets: Asset[];
  onClose: () => void;
}

function TemplateModal({ template, sites, assets, onClose }: TemplateModalProps) {
  const queryClient = useQueryClient();
  const isEdit = !!template;

  const [form, setForm] = useState({
    title: template?.title || '',
    description: template?.description || '',
    priority: template?.priority || WorkOrderPriority.SCHEDULED,
    recurrence_type: template?.recurrence_type || RecurrenceType.MONTHLY,
    recurrence_interval: template?.recurrence_interval || 1,
    site_id: template?.site_id || '',
    asset_id: template?.asset_id || '',
    assigned_to_role: template?.assigned_to_role || 'TECHNICIAN',
    required_cert: template?.required_cert || '',
    is_active: template?.is_active ?? true,
    checklist_json: template?.checklist_json || [''],
  });

  const updateField = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const saveMutation = useMutation({
    mutationFn: async () => {
      const data = {
        ...form,
        checklist_json: form.checklist_json.filter((item) => item.trim()),
        site_id: form.site_id || undefined,
        asset_id: form.asset_id || undefined,
        required_cert: form.required_cert || undefined,
      };
      if (isEdit) {
        return pmApi.updateTemplate(template!.id, data);
      }
      return pmApi.createTemplate(data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pm-templates'] });
      onClose();
    },
  });

  const addChecklistItem = () => {
    updateField('checklist_json', [...form.checklist_json, '']);
  };

  const updateChecklistItem = (index: number, value: string) => {
    const updated = [...form.checklist_json];
    updated[index] = value;
    updateField('checklist_json', updated);
  };

  const removeChecklistItem = (index: number) => {
    const updated = form.checklist_json.filter((_, i) => i !== index);
    updateField('checklist_json', updated.length > 0 ? updated : ['']);
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-end md:items-center justify-center z-50">
      <div className="bg-white rounded-t-2xl md:rounded-xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between z-10">
          <h2 className="text-lg font-semibold text-gray-900">
            {isEdit ? 'Edit Template' : 'New PM Template'}
          </h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg min-h-[48px] min-w-[48px] flex items-center justify-center"
          >
            <X size={20} />
          </button>
        </div>

        <div className="p-6 space-y-4">
          {/* Name */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Template Name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={form.title}
              onChange={(e) => updateField('title', e.target.value)}
              placeholder="e.g. Monthly Compressor Inspection"
              className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm min-h-[48px] focus:ring-2 focus:ring-navy-500 focus:border-navy-500"
            />
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
            <textarea
              value={form.description}
              onChange={(e) => updateField('description', e.target.value)}
              rows={3}
              placeholder="Describe the PM procedure..."
              className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-navy-500 focus:border-navy-500"
            />
          </div>

          {/* Priority + Recurrence */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Priority</label>
              <select
                value={form.priority}
                onChange={(e) => updateField('priority', e.target.value as WorkOrderPriority)}
                className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm min-h-[48px] bg-white"
              >
                {Object.values(WorkOrderPriority).map((p) => (
                  <option key={p} value={p}>{p}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Recurrence</label>
              <select
                value={form.recurrence_type}
                onChange={(e) => updateField('recurrence_type', e.target.value as RecurrenceType)}
                className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm min-h-[48px] bg-white"
              >
                {Object.entries(recurrenceLabels).map(([val, label]) => (
                  <option key={val} value={val}>{label}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Interval */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Recurrence Interval
            </label>
            <input
              type="number"
              min={1}
              value={form.recurrence_interval}
              onChange={(e) => updateField('recurrence_interval', parseInt(e.target.value) || 1)}
              className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm min-h-[48px] focus:ring-2 focus:ring-navy-500 focus:border-navy-500"
            />
            <p className="text-xs text-gray-400 mt-1">
              Every {form.recurrence_interval} {form.recurrence_type === RecurrenceType.DAILY ? 'day(s)' :
                form.recurrence_type === RecurrenceType.WEEKLY ? 'week(s)' :
                form.recurrence_type === RecurrenceType.MONTHLY ? 'month(s)' : 'interval(s)'}
            </p>
          </div>

          {/* Site + Asset */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Site</label>
              <select
                value={form.site_id}
                onChange={(e) => updateField('site_id', e.target.value)}
                className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm min-h-[48px] bg-white"
              >
                <option value="">None</option>
                {sites.map((s) => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Asset</label>
              <select
                value={form.asset_id}
                onChange={(e) => updateField('asset_id', e.target.value)}
                className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm min-h-[48px] bg-white"
              >
                <option value="">None</option>
                {assets.map((a) => (
                  <option key={a.id} value={a.id}>{a.name}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Assigned Role */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Assigned To Role</label>
            <select
              value={form.assigned_to_role}
              onChange={(e) => updateField('assigned_to_role', e.target.value)}
              className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm min-h-[48px] bg-white"
            >
              <option value="TECHNICIAN">Technician</option>
              <option value="OPERATOR">Operator</option>
              <option value="SUPERVISOR">Supervisor</option>
            </select>
          </div>

          {/* Required Cert */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Required Certification</label>
            <input
              type="text"
              value={form.required_cert}
              onChange={(e) => updateField('required_cert', e.target.value)}
              placeholder="e.g. H2S Alive"
              className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm min-h-[48px] focus:ring-2 focus:ring-navy-500 focus:border-navy-500"
            />
          </div>

          {/* Checklist */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Checklist Items</label>
            <div className="space-y-2">
              {form.checklist_json.map((item, index) => (
                <div key={index} className="flex items-center gap-2">
                  <span className="text-xs text-gray-400 w-5 text-right shrink-0">{index + 1}.</span>
                  <input
                    type="text"
                    value={item}
                    onChange={(e) => updateChecklistItem(index, e.target.value)}
                    placeholder="Checklist step..."
                    className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm min-h-[48px] focus:ring-2 focus:ring-navy-500 focus:border-navy-500"
                  />
                  <button
                    onClick={() => removeChecklistItem(index)}
                    className="p-2 hover:bg-red-50 rounded-lg min-h-[48px] min-w-[48px] flex items-center justify-center"
                    aria-label="Remove item"
                  >
                    <Trash2 size={14} className="text-red-500" />
                  </button>
                </div>
              ))}
            </div>
            <button
              onClick={addChecklistItem}
              className="mt-2 flex items-center gap-1 text-sm text-navy-600 font-medium px-2 py-2 min-h-[48px]"
            >
              <Plus size={14} /> Add Item
            </button>
          </div>

          {/* Active toggle */}
          <div className="flex items-center justify-between py-2">
            <span className="text-sm font-medium text-gray-700">Active</span>
            <button
              onClick={() => updateField('is_active', !form.is_active)}
              className="min-h-[48px] min-w-[48px] flex items-center justify-center"
            >
              {form.is_active ? (
                <ToggleRight size={28} className="text-green-600" />
              ) : (
                <ToggleLeft size={28} className="text-gray-400" />
              )}
            </button>
          </div>
        </div>

        {/* Footer */}
        <div className="sticky bottom-0 bg-white border-t border-gray-200 px-6 py-4 flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2.5 border border-gray-300 rounded-lg font-medium text-gray-700 min-h-[48px]"
          >
            Cancel
          </button>
          <button
            onClick={() => saveMutation.mutate()}
            disabled={!form.title.trim() || saveMutation.isPending}
            className="flex-1 px-4 py-2.5 bg-navy-900 text-white rounded-lg font-medium min-h-[48px] disabled:opacity-50"
          >
            {saveMutation.isPending ? 'Saving...' : isEdit ? 'Update Template' : 'Create Template'}
          </button>
        </div>
      </div>
    </div>
  );
}
