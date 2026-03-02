import { useState, useMemo, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  BarChart3, Clock, ShieldCheck, Package, DollarSign, Wallet, Wrench,
  Users, AlertTriangle, Download, CalendarDays, Loader2, Filter,
  TrendingUp, TrendingDown, Minus, CheckCircle2, XCircle,
} from 'lucide-react';
import { format, subDays, startOfYear, parseISO } from 'date-fns';
import { reportsApi, type ReportFilters } from '@/api/reports';
import { sitesApi } from '@/api/sites';
import type { Site, Area } from '@/types/api';
import { formatCurrency, formatNumber, formatPercentage, formatMinutesAsHours } from '@/utils/numberFormat';

type ReportTab =
  | 'overview'
  | 'response-times'
  | 'sla-compliance'
  | 'parts-spend'
  | 'labor-cost'
  | 'budget'
  | 'pm-completion'
  | 'technician-performance'
  | 'safety-flags';

type DatePreset = '7d' | '30d' | '90d' | 'ytd' | 'custom';

const reportTabs: { key: ReportTab; label: string; icon: React.ElementType }[] = [
  { key: 'overview', label: 'Overview', icon: BarChart3 },
  { key: 'response-times', label: 'Response Times', icon: Clock },
  { key: 'sla-compliance', label: 'SLA Compliance', icon: ShieldCheck },
  { key: 'parts-spend', label: 'Parts Spend', icon: Package },
  { key: 'labor-cost', label: 'Labor Cost', icon: DollarSign },
  { key: 'budget', label: 'Budget', icon: Wallet },
  { key: 'pm-completion', label: 'PM Completion', icon: Wrench },
  { key: 'technician-performance', label: 'Tech Performance', icon: Users },
  { key: 'safety-flags', label: 'Safety Flags', icon: AlertTriangle },
];

function getDateRange(preset: DatePreset, customFrom?: string, customTo?: string): { from: string; to: string } {
  const today = new Date();
  const toStr = format(today, 'yyyy-MM-dd');

  switch (preset) {
    case '7d':
      return { from: format(subDays(today, 7), 'yyyy-MM-dd'), to: toStr };
    case '30d':
      return { from: format(subDays(today, 30), 'yyyy-MM-dd'), to: toStr };
    case '90d':
      return { from: format(subDays(today, 90), 'yyyy-MM-dd'), to: toStr };
    case 'ytd':
      return { from: format(startOfYear(today), 'yyyy-MM-dd'), to: toStr };
    case 'custom':
      return { from: customFrom || toStr, to: customTo || toStr };
    default:
      return { from: format(subDays(today, 30), 'yyyy-MM-dd'), to: toStr };
  }
}

const reportApiFns: Record<ReportTab, (filters: ReportFilters) => ReturnType<typeof reportsApi.workOrders>> = {
  'overview': reportsApi.workOrders,
  'response-times': reportsApi.responseTimes,
  'sla-compliance': reportsApi.slaCompliance,
  'parts-spend': reportsApi.partsSpend,
  'labor-cost': reportsApi.laborCost,
  'budget': reportsApi.budget,
  'pm-completion': reportsApi.pmCompletion,
  'technician-performance': reportsApi.technicianPerformance,
  'safety-flags': reportsApi.safetyFlags,
};

export default function ReportsPage() {
  const [activeTab, setActiveTab] = useState<ReportTab>('overview');
  const [datePreset, setDatePreset] = useState<DatePreset>('30d');
  const [customFrom, setCustomFrom] = useState('');
  const [customTo, setCustomTo] = useState('');
  const [areaFilter, setAreaFilter] = useState('');

  const dateRange = useMemo(
    () => getDateRange(datePreset, customFrom, customTo),
    [datePreset, customFrom, customTo]
  );

  const filters: ReportFilters = useMemo(() => ({
    date_from: dateRange.from,
    date_to: dateRange.to,
    area_id: areaFilter || undefined,
  }), [dateRange, areaFilter]);

  // Fetch report data
  const { data: reportData, isLoading, error } = useQuery({
    queryKey: ['report', activeTab, filters],
    queryFn: async () => {
      const apiFn = reportApiFns[activeTab];
      const res = await apiFn(filters);
      return res.data;
    },
  });

  // Fetch areas for filter
  const { data: sites = [] } = useQuery({
    queryKey: ['sites-for-filter'],
    queryFn: async () => {
      const res = await sitesApi.list();
      return res.data;
    },
  });

  // CSV export handler
  const handleExportCsv = useCallback(async () => {
    try {
      const apiFn = reportApiFns[activeTab];
      const res = await apiFn({ ...filters, format: 'csv' });
      const blob = new Blob([res.data as BlobPart], { type: 'text/csv' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${activeTab}-report-${dateRange.from}-to-${dateRange.to}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch {
      // Export failed silently
    }
  }, [activeTab, filters, dateRange]);

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Reports & Analytics</h1>
        <button
          onClick={handleExportCsv}
          className="flex items-center gap-2 px-4 py-2.5 bg-white border border-gray-300 rounded-lg font-medium text-gray-700 min-h-[48px] hover:bg-gray-50 transition-colors"
        >
          <Download size={16} />
          Export CSV
        </button>
      </div>

      {/* Tab selector (horizontal scroll on mobile) */}
      <div className="overflow-x-auto -mx-4 px-4">
        <div className="flex gap-1 min-w-max pb-2">
          {reportTabs.map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              onClick={() => setActiveTab(key)}
              className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium whitespace-nowrap min-h-[48px] transition-colors ${
                activeTab === key
                  ? 'bg-navy-900 text-white'
                  : 'bg-white text-gray-600 border border-gray-200 hover:bg-gray-50'
              }`}
            >
              <Icon size={14} />
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Date range + Area filter */}
      <div className="flex flex-wrap gap-3 items-end bg-white rounded-lg border border-gray-200 p-4">
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Date Range</label>
          <div className="flex gap-1">
            {(['7d', '30d', '90d', 'ytd', 'custom'] as DatePreset[]).map((preset) => (
              <button
                key={preset}
                onClick={() => setDatePreset(preset)}
                className={`px-3 py-2 rounded-lg text-sm font-medium min-h-[48px] transition-colors ${
                  datePreset === preset
                    ? 'bg-navy-100 text-navy-900 border border-navy-300'
                    : 'bg-gray-50 text-gray-600 border border-gray-200 hover:bg-gray-100'
                }`}
              >
                {preset === 'ytd' ? 'YTD' : preset === 'custom' ? 'Custom' : preset.toUpperCase()}
              </button>
            ))}
          </div>
        </div>

        {datePreset === 'custom' && (
          <div className="flex gap-2">
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">From</label>
              <input
                type="date"
                value={customFrom}
                onChange={(e) => setCustomFrom(e.target.value)}
                className="px-3 py-2 border border-gray-300 rounded-lg text-sm min-h-[48px]"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">To</label>
              <input
                type="date"
                value={customTo}
                onChange={(e) => setCustomTo(e.target.value)}
                className="px-3 py-2 border border-gray-300 rounded-lg text-sm min-h-[48px]"
              />
            </div>
          </div>
        )}

        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Area</label>
          <select
            value={areaFilter}
            onChange={(e) => setAreaFilter(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm min-h-[48px] bg-white"
          >
            <option value="">All Areas</option>
            {/* Areas derived from sites; in production would use a separate areas endpoint */}
            {Array.from(new Set(sites.map((s: Site) => s.location_id))).map((locId) => (
              <option key={locId as string} value={locId as string}>
                {(locId as string).slice(0, 8)}...
              </option>
            ))}
          </select>
        </div>

        <div className="text-xs text-gray-400">
          {dateRange.from} to {dateRange.to}
        </div>
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="flex items-center justify-center py-16">
          <Loader2 size={32} className="animate-spin text-navy-600" />
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-sm">
          Failed to load report data. Please try again.
        </div>
      )}

      {/* Report content */}
      {!isLoading && !error && reportData && (
        <div className="space-y-4">
          {activeTab === 'overview' && <OverviewReport data={reportData} />}
          {activeTab === 'response-times' && <ResponseTimesReport data={reportData} />}
          {activeTab === 'sla-compliance' && <SLAComplianceReport data={reportData} />}
          {activeTab === 'parts-spend' && <GenericTableReport data={reportData} title="Parts Spend" valueKey="total_cost" valueFormatter={formatCurrency} />}
          {activeTab === 'labor-cost' && <GenericTableReport data={reportData} title="Labor Cost" valueKey="total_cost" valueFormatter={formatCurrency} />}
          {activeTab === 'budget' && <BudgetReport data={reportData} />}
          {activeTab === 'pm-completion' && <PMCompletionReport data={reportData} />}
          {activeTab === 'technician-performance' && <TechPerformanceReport data={reportData} />}
          {activeTab === 'safety-flags' && <SafetyFlagsReport data={reportData} />}
        </div>
      )}
    </div>
  );
}

// ── Overview Report ─────────────────────────────────────────────────────────

function OverviewReport({ data }: { data: Record<string, unknown> }) {
  const d = data as {
    total_count?: number;
    by_status?: Record<string, number>;
    by_priority?: Record<string, number>;
    by_type?: Record<string, number>;
    safety_flag_count?: number;
    escalated_count?: number;
  };

  const statusColors: Record<string, string> = {
    NEW: 'bg-blue-100 text-blue-800',
    ASSIGNED: 'bg-indigo-100 text-indigo-800',
    ACCEPTED: 'bg-cyan-100 text-cyan-800',
    IN_PROGRESS: 'bg-yellow-100 text-yellow-800',
    WAITING_ON_OPS: 'bg-orange-100 text-orange-800',
    WAITING_ON_PARTS: 'bg-orange-100 text-orange-800',
    RESOLVED: 'bg-green-100 text-green-800',
    VERIFIED: 'bg-emerald-100 text-emerald-800',
    CLOSED: 'bg-gray-100 text-gray-600',
    ESCALATED: 'bg-red-100 text-red-800',
  };

  const priorityColors: Record<string, string> = {
    IMMEDIATE: 'bg-red-100 text-red-800 border-red-200',
    URGENT: 'bg-orange-100 text-orange-800 border-orange-200',
    SCHEDULED: 'bg-yellow-100 text-yellow-800 border-yellow-200',
    DEFERRED: 'bg-gray-100 text-gray-700 border-gray-200',
  };

  return (
    <div className="space-y-4">
      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard label="Total Work Orders" value={formatNumber(d.total_count || 0)} icon={BarChart3} />
        <StatCard
          label="Safety Flags"
          value={formatNumber(d.safety_flag_count || 0)}
          icon={AlertTriangle}
          valueColor={d.safety_flag_count ? 'text-red-600' : undefined}
          bgColor={d.safety_flag_count ? 'bg-red-50 border-red-200' : undefined}
        />
        <StatCard
          label="Escalated"
          value={formatNumber(d.escalated_count || 0)}
          icon={TrendingUp}
          valueColor={d.escalated_count ? 'text-orange-600' : undefined}
        />
        <StatCard
          label="Open"
          value={formatNumber(
            Object.entries(d.by_status || {})
              .filter(([k]) => !['CLOSED', 'VERIFIED'].includes(k))
              .reduce((sum, [, v]) => sum + v, 0)
          )}
          icon={Wrench}
        />
      </div>

      {/* By Priority */}
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <h3 className="font-semibold text-gray-900 mb-3">By Priority</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {Object.entries(d.by_priority || {}).map(([priority, count]) => (
            <div
              key={priority}
              className={`rounded-lg border p-3 ${priorityColors[priority] || 'bg-gray-100 text-gray-800'}`}
            >
              <div className="text-2xl font-bold">{count}</div>
              <div className="text-xs font-medium">{priority}</div>
            </div>
          ))}
        </div>
      </div>

      {/* By Status */}
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <h3 className="font-semibold text-gray-900 mb-3">By Status</h3>
        <div className="space-y-2">
          {Object.entries(d.by_status || {}).map(([status, count]) => {
            const total = d.total_count || 1;
            const pct = ((count as number) / total) * 100;
            return (
              <div key={status} className="flex items-center gap-3">
                <span className={`text-xs font-medium rounded-full px-2 py-0.5 ${statusColors[status] || 'bg-gray-100'} w-32 text-center`}>
                  {status.replace(/_/g, ' ')}
                </span>
                <div className="flex-1 bg-gray-100 rounded-full h-2.5">
                  <div
                    className="h-2.5 rounded-full bg-navy-600 transition-all"
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <span className="text-sm font-semibold text-gray-900 w-10 text-right">{count as number}</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* By Type */}
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <h3 className="font-semibold text-gray-900 mb-3">By Type</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {Object.entries(d.by_type || {}).map(([type, count]) => (
            <div key={type} className="bg-gray-50 rounded-lg p-3 text-center">
              <div className="text-xl font-bold text-gray-900">{count as number}</div>
              <div className="text-xs text-gray-500">{type}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Response Times Report ────────────────────────────────────────────────────

function ResponseTimesReport({ data }: { data: Record<string, unknown> }) {
  const d = data as {
    avg_ack_minutes?: number;
    avg_first_update_minutes?: number;
    avg_resolve_hours?: number;
    by_priority?: Array<{
      priority: string;
      avg_ack_minutes: number;
      avg_resolve_hours: number;
      count: number;
    }>;
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <StatCard
          label="Avg Acknowledgement"
          value={formatMinutesAsHours(d.avg_ack_minutes || 0)}
          icon={Clock}
        />
        <StatCard
          label="Avg First Update"
          value={formatMinutesAsHours(d.avg_first_update_minutes || 0)}
          icon={Clock}
        />
        <StatCard
          label="Avg Resolution"
          value={`${(d.avg_resolve_hours || 0).toFixed(1)}h`}
          icon={Clock}
        />
      </div>

      {d.by_priority && d.by_priority.length > 0 && (
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-200">
            <h3 className="font-semibold text-gray-900">By Priority</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Priority</th>
                  <th className="text-right px-4 py-3 font-medium text-gray-500">Count</th>
                  <th className="text-right px-4 py-3 font-medium text-gray-500">Avg Ack</th>
                  <th className="text-right px-4 py-3 font-medium text-gray-500">Avg Resolution</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {d.by_priority.map((row) => (
                  <tr key={row.priority} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium text-gray-900">{row.priority}</td>
                    <td className="px-4 py-3 text-right text-gray-600">{row.count}</td>
                    <td className="px-4 py-3 text-right text-gray-600">
                      {formatMinutesAsHours(row.avg_ack_minutes)}
                    </td>
                    <td className="px-4 py-3 text-right text-gray-600">
                      {row.avg_resolve_hours.toFixed(1)}h
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

// ── SLA Compliance Report ───────────────────────────────────────────────────

function SLAComplianceReport({ data }: { data: Record<string, unknown> }) {
  const d = data as {
    ack_compliance_pct?: number;
    resolve_compliance_pct?: number;
    overall_compliance_pct?: number;
    total_breaches?: number;
    by_priority?: Array<{
      priority: string;
      ack_pct: number;
      resolve_pct: number;
      breaches: number;
    }>;
  };

  const getComplianceColor = (pct: number) => {
    if (pct >= 95) return 'text-green-600';
    if (pct >= 80) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getComplianceBg = (pct: number) => {
    if (pct >= 95) return 'bg-green-50 border-green-200';
    if (pct >= 80) return 'bg-yellow-50 border-yellow-200';
    return 'bg-red-50 border-red-200';
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className={`rounded-lg border p-4 ${getComplianceBg(d.overall_compliance_pct || 0)}`}>
          <div className="text-xs font-medium text-gray-500 mb-1">Overall</div>
          <div className={`text-3xl font-bold ${getComplianceColor(d.overall_compliance_pct || 0)}`}>
            {formatPercentage(d.overall_compliance_pct || 0)}
          </div>
        </div>
        <div className={`rounded-lg border p-4 ${getComplianceBg(d.ack_compliance_pct || 0)}`}>
          <div className="text-xs font-medium text-gray-500 mb-1">Ack Compliance</div>
          <div className={`text-3xl font-bold ${getComplianceColor(d.ack_compliance_pct || 0)}`}>
            {formatPercentage(d.ack_compliance_pct || 0)}
          </div>
        </div>
        <div className={`rounded-lg border p-4 ${getComplianceBg(d.resolve_compliance_pct || 0)}`}>
          <div className="text-xs font-medium text-gray-500 mb-1">Resolve Compliance</div>
          <div className={`text-3xl font-bold ${getComplianceColor(d.resolve_compliance_pct || 0)}`}>
            {formatPercentage(d.resolve_compliance_pct || 0)}
          </div>
        </div>
        <StatCard
          label="Total Breaches"
          value={formatNumber(d.total_breaches || 0)}
          icon={XCircle}
          valueColor={d.total_breaches ? 'text-red-600' : undefined}
          bgColor={d.total_breaches ? 'bg-red-50 border-red-200' : undefined}
        />
      </div>

      {d.by_priority && d.by_priority.length > 0 && (
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-200">
            <h3 className="font-semibold text-gray-900">Compliance by Priority</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Priority</th>
                  <th className="text-right px-4 py-3 font-medium text-gray-500">Ack %</th>
                  <th className="text-right px-4 py-3 font-medium text-gray-500">Resolve %</th>
                  <th className="text-right px-4 py-3 font-medium text-gray-500">Breaches</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {d.by_priority.map((row) => (
                  <tr key={row.priority} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium text-gray-900">{row.priority}</td>
                    <td className={`px-4 py-3 text-right font-semibold ${getComplianceColor(row.ack_pct)}`}>
                      {formatPercentage(row.ack_pct)}
                    </td>
                    <td className={`px-4 py-3 text-right font-semibold ${getComplianceColor(row.resolve_pct)}`}>
                      {formatPercentage(row.resolve_pct)}
                    </td>
                    <td className={`px-4 py-3 text-right ${row.breaches > 0 ? 'text-red-600 font-semibold' : 'text-gray-600'}`}>
                      {row.breaches}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Budget Report ───────────────────────────────────────────────────────────

function BudgetReport({ data }: { data: Record<string, unknown> }) {
  const d = data as {
    total_budget?: number;
    total_actual?: number;
    total_variance?: number;
    by_area?: Array<{
      area_name: string;
      budget: number;
      actual: number;
      variance: number;
      over_budget: boolean;
    }>;
  };

  const overBudget = (d.total_variance || 0) < 0;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <StatCard label="Total Budget" value={formatCurrency(d.total_budget || 0)} icon={Wallet} />
        <StatCard
          label="Total Actual"
          value={formatCurrency(d.total_actual || 0)}
          icon={DollarSign}
          valueColor={overBudget ? 'text-red-600' : undefined}
        />
        <StatCard
          label="Variance"
          value={formatCurrency(Math.abs(d.total_variance || 0))}
          icon={overBudget ? TrendingDown : TrendingUp}
          valueColor={overBudget ? 'text-red-600' : 'text-green-600'}
          bgColor={overBudget ? 'bg-red-50 border-red-200' : 'bg-green-50 border-green-200'}
        />
      </div>

      {d.by_area && d.by_area.length > 0 && (
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-200">
            <h3 className="font-semibold text-gray-900">Budget vs Actual by Area</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Area</th>
                  <th className="text-right px-4 py-3 font-medium text-gray-500">Budget</th>
                  <th className="text-right px-4 py-3 font-medium text-gray-500">Actual</th>
                  <th className="text-right px-4 py-3 font-medium text-gray-500">Variance</th>
                  <th className="text-center px-4 py-3 font-medium text-gray-500">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {d.by_area.map((row) => (
                  <tr key={row.area_name} className={`hover:bg-gray-50 ${row.over_budget ? 'bg-red-50' : ''}`}>
                    <td className="px-4 py-3 font-medium text-gray-900">{row.area_name}</td>
                    <td className="px-4 py-3 text-right text-gray-600">{formatCurrency(row.budget)}</td>
                    <td className={`px-4 py-3 text-right font-medium ${row.over_budget ? 'text-red-600' : 'text-gray-900'}`}>
                      {formatCurrency(row.actual)}
                    </td>
                    <td className={`px-4 py-3 text-right font-semibold ${row.variance < 0 ? 'text-red-600' : 'text-green-600'}`}>
                      {row.variance < 0 ? '-' : '+'}{formatCurrency(Math.abs(row.variance))}
                    </td>
                    <td className="px-4 py-3 text-center">
                      {row.over_budget ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-red-100 text-red-700 text-xs rounded-full font-semibold">
                          <AlertTriangle size={10} />
                          Over
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-green-100 text-green-700 text-xs rounded-full font-semibold">
                          <CheckCircle2 size={10} />
                          On Track
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

// ── PM Completion Report ────────────────────────────────────────────────────

function PMCompletionReport({ data }: { data: Record<string, unknown> }) {
  const d = data as {
    total_scheduled?: number;
    completed?: number;
    skipped?: number;
    overdue?: number;
    completion_pct?: number;
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard label="Total Scheduled" value={formatNumber(d.total_scheduled || 0)} icon={CalendarDays} />
        <StatCard
          label="Completed"
          value={formatNumber(d.completed || 0)}
          icon={CheckCircle2}
          valueColor="text-green-600"
        />
        <StatCard
          label="Overdue"
          value={formatNumber(d.overdue || 0)}
          icon={AlertTriangle}
          valueColor={d.overdue ? 'text-red-600' : undefined}
          bgColor={d.overdue ? 'bg-red-50 border-red-200' : undefined}
        />
        <StatCard
          label="Completion Rate"
          value={formatPercentage(d.completion_pct || 0)}
          icon={BarChart3}
          valueColor={(d.completion_pct || 0) >= 90 ? 'text-green-600' : 'text-orange-600'}
        />
      </div>

      {/* Visual completion bar */}
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <h3 className="font-semibold text-gray-900 mb-3">Completion Overview</h3>
        <div className="bg-gray-100 rounded-full h-6 overflow-hidden flex">
          {(d.completed || 0) > 0 && (
            <div
              className="bg-green-500 h-full transition-all flex items-center justify-center text-xs text-white font-medium"
              style={{ width: `${((d.completed || 0) / (d.total_scheduled || 1)) * 100}%` }}
            >
              {d.completed}
            </div>
          )}
          {(d.skipped || 0) > 0 && (
            <div
              className="bg-gray-400 h-full transition-all flex items-center justify-center text-xs text-white font-medium"
              style={{ width: `${((d.skipped || 0) / (d.total_scheduled || 1)) * 100}%` }}
            >
              {d.skipped}
            </div>
          )}
          {(d.overdue || 0) > 0 && (
            <div
              className="bg-red-500 h-full transition-all flex items-center justify-center text-xs text-white font-medium"
              style={{ width: `${((d.overdue || 0) / (d.total_scheduled || 1)) * 100}%` }}
            >
              {d.overdue}
            </div>
          )}
        </div>
        <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
          <span className="flex items-center gap-1"><div className="w-2.5 h-2.5 rounded bg-green-500" /> Completed</span>
          <span className="flex items-center gap-1"><div className="w-2.5 h-2.5 rounded bg-gray-400" /> Skipped</span>
          <span className="flex items-center gap-1"><div className="w-2.5 h-2.5 rounded bg-red-500" /> Overdue</span>
        </div>
      </div>
    </div>
  );
}

// ── Technician Performance Report ───────────────────────────────────────────

function TechPerformanceReport({ data }: { data: Record<string, unknown> }) {
  const d = data as {
    technicians?: Array<{
      name: string;
      assigned: number;
      completed: number;
      completion_pct: number;
      avg_resolution_minutes: number;
    }>;
  };

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-200">
          <h3 className="font-semibold text-gray-900">Technician Performance</h3>
        </div>

        {(!d.technicians || d.technicians.length === 0) && (
          <div className="text-center py-8 text-gray-500 text-sm">
            No technician data available for this period.
          </div>
        )}

        {d.technicians && d.technicians.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Technician</th>
                  <th className="text-right px-4 py-3 font-medium text-gray-500">Assigned</th>
                  <th className="text-right px-4 py-3 font-medium text-gray-500">Completed</th>
                  <th className="text-right px-4 py-3 font-medium text-gray-500">Completion %</th>
                  <th className="text-right px-4 py-3 font-medium text-gray-500">Avg Resolution</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {d.technicians.map((tech) => (
                  <tr key={tech.name} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium text-gray-900">{tech.name}</td>
                    <td className="px-4 py-3 text-right text-gray-600">{tech.assigned}</td>
                    <td className="px-4 py-3 text-right text-gray-600">{tech.completed}</td>
                    <td className={`px-4 py-3 text-right font-semibold ${
                      tech.completion_pct >= 90 ? 'text-green-600' :
                      tech.completion_pct >= 70 ? 'text-yellow-600' : 'text-red-600'
                    }`}>
                      {formatPercentage(tech.completion_pct)}
                    </td>
                    <td className="px-4 py-3 text-right text-gray-600">
                      {formatMinutesAsHours(tech.avg_resolution_minutes)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Safety Flags Report ─────────────────────────────────────────────────────

function SafetyFlagsReport({ data }: { data: Record<string, unknown> }) {
  const d = data as {
    total_flags?: number;
    open_flags?: number;
    resolved_flags?: number;
    by_site?: Array<{ site_name: string; count: number }>;
    recent?: Array<{
      wo_number: string;
      title: string;
      site_name: string;
      safety_notes: string;
      created_at: string;
      status: string;
    }>;
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <StatCard
          label="Total Safety Flags"
          value={formatNumber(d.total_flags || 0)}
          icon={AlertTriangle}
          valueColor="text-red-600"
          bgColor="bg-red-50 border-red-200"
        />
        <StatCard
          label="Open"
          value={formatNumber(d.open_flags || 0)}
          icon={AlertTriangle}
          valueColor={d.open_flags ? 'text-red-600' : undefined}
        />
        <StatCard
          label="Resolved"
          value={formatNumber(d.resolved_flags || 0)}
          icon={CheckCircle2}
          valueColor="text-green-600"
        />
      </div>

      {d.recent && d.recent.length > 0 && (
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-200">
            <h3 className="font-semibold text-gray-900">Recent Safety-Flagged Work Orders</h3>
          </div>
          <div className="divide-y divide-gray-100">
            {d.recent.map((wo, idx) => (
              <div key={idx} className="px-4 py-3">
                <div className="flex items-center gap-2 mb-1">
                  <AlertTriangle size={14} className="text-red-600 shrink-0" />
                  <span className="font-mono text-xs text-gray-500">{wo.wo_number}</span>
                  <span className="font-medium text-gray-900 text-sm truncate">{wo.title}</span>
                </div>
                <div className="ml-5 text-xs text-gray-500 space-y-0.5">
                  <div>{wo.site_name} &middot; {wo.status}</div>
                  {wo.safety_notes && (
                    <div className="text-red-600 font-medium">{wo.safety_notes}</div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Generic Table Report ────────────────────────────────────────────────────

function GenericTableReport({
  data,
  title,
  valueKey,
  valueFormatter,
}: {
  data: Record<string, unknown>;
  title: string;
  valueKey: string;
  valueFormatter: (v: number) => string;
}) {
  const d = data as {
    total?: number;
    items?: Array<Record<string, unknown>>;
  };

  return (
    <div className="space-y-4">
      <StatCard
        label={`Total ${title}`}
        value={valueFormatter(d.total || 0)}
        icon={DollarSign}
      />

      {d.items && d.items.length > 0 && (
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-200">
            <h3 className="font-semibold text-gray-900">{title} Breakdown</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  {Object.keys(d.items[0]).map((col) => (
                    <th
                      key={col}
                      className={`px-4 py-3 font-medium text-gray-500 ${
                        col === valueKey ? 'text-right' : 'text-left'
                      }`}
                    >
                      {col.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {d.items.map((row, idx) => (
                  <tr key={idx} className="hover:bg-gray-50">
                    {Object.entries(row).map(([col, val]) => (
                      <td
                        key={col}
                        className={`px-4 py-3 ${col === valueKey ? 'text-right font-semibold text-gray-900' : 'text-gray-600'}`}
                      >
                        {col === valueKey ? valueFormatter(val as number) : String(val)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Stat Card ───────────────────────────────────────────────────────────────

function StatCard({
  label,
  value,
  icon: Icon,
  valueColor,
  bgColor,
}: {
  label: string;
  value: string;
  icon: React.ElementType;
  valueColor?: string;
  bgColor?: string;
}) {
  return (
    <div className={`rounded-lg border p-4 ${bgColor || 'bg-white border-gray-200'}`}>
      <div className="flex items-center gap-2 text-gray-500 text-xs mb-1">
        <Icon size={14} />
        {label}
      </div>
      <div className={`text-2xl font-bold ${valueColor || 'text-gray-900'}`}>{value}</div>
    </div>
  );
}
