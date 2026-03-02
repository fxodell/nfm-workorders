import { useState, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Plus, RefreshCw, ChevronDown, ChevronRight, AlertTriangle,
  Clock, MapPin, Loader2, ArrowUpCircle, ShieldAlert, ClipboardList,
} from 'lucide-react';
import { format } from 'date-fns';
import { dashboardApi } from '@/api/dashboard';
import { useAuthStore } from '@/stores/authStore';
import { useUIStore } from '@/stores/uiStore';
import type { AreaDashboard, SiteDashboard } from '@/types/api';
import { WorkOrderPriority, SiteType } from '@/types/enums';
import { getPriorityConfig } from '@/utils/priority';

// ------- Sub-components -------

function StatCard({
  label,
  value,
  icon: Icon,
  bgColor,
  textColor,
  onClick,
}: {
  label: string;
  value: number;
  icon: React.ComponentType<{ size?: number; className?: string }>;
  bgColor: string;
  textColor: string;
  onClick?: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex flex-col items-center justify-center rounded-xl p-4 min-h-[88px] min-w-0 flex-1 transition-transform active:scale-95 ${bgColor}`}
    >
      <Icon size={22} className={textColor} />
      <span className={`text-2xl font-bold mt-1 ${textColor}`}>{value}</span>
      <span className={`text-xs font-medium ${textColor} opacity-80`}>{label}</span>
    </button>
  );
}

function SiteRow({ site }: { site: SiteDashboard }) {
  const navigate = useNavigate();

  const siteTypeLabels: Record<string, string> = {
    [SiteType.WELL_SITE]: 'Well Site',
    [SiteType.PLANT]: 'Plant',
    [SiteType.BUILDING]: 'Building',
    [SiteType.COMPRESSOR_STATION]: 'Compressor',
    [SiteType.TANK_BATTERY]: 'Tank Battery',
    [SiteType.SEPARATOR]: 'Separator',
    [SiteType.LINE]: 'Line',
    [SiteType.SUITE]: 'Suite',
    [SiteType.APARTMENT]: 'Apartment',
    [SiteType.OTHER]: 'Other',
  };

  return (
    <button
      onClick={() => navigate(`/sites/${site.site_id}`)}
      className="flex items-center justify-between w-full px-4 py-3 hover:bg-gray-50 active:bg-gray-100 min-h-[48px] transition-colors border-b border-gray-100 last:border-b-0 text-left"
    >
      <div className="flex items-center gap-3 min-w-0 flex-1">
        <MapPin size={16} className="text-gray-400 shrink-0" />
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-gray-900 truncate">{site.site_name}</span>
            {site.safety_flag && <AlertTriangle size={14} className="text-red-600 shrink-0" />}
            {site.escalated && <ArrowUpCircle size={14} className="text-red-500 shrink-0" />}
          </div>
          <span className="text-xs text-gray-500">
            {siteTypeLabels[site.site_type] || site.site_type}
          </span>
        </div>
      </div>

      <div className="flex items-center gap-3 shrink-0">
        {site.wo_count > 0 && (
          <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
            site.highest_priority === WorkOrderPriority.IMMEDIATE
              ? 'bg-red-100 text-red-700'
              : site.highest_priority === WorkOrderPriority.URGENT
                ? 'bg-orange-100 text-orange-700'
                : 'bg-gray-100 text-gray-700'
          }`}>
            {site.wo_count} WO{site.wo_count !== 1 ? 's' : ''}
          </span>
        )}

        {site.assigned_techs.length > 0 && (
          <div className="flex -space-x-2">
            {site.assigned_techs.slice(0, 3).map((tech) => (
              <div
                key={tech.id}
                className="w-6 h-6 rounded-full bg-navy-200 border-2 border-white flex items-center justify-center text-[10px] font-semibold text-navy-800"
                title={tech.name}
              >
                {tech.name?.charAt(0).toUpperCase() || '?'}
              </div>
            ))}
            {site.assigned_techs.length > 3 && (
              <div className="w-6 h-6 rounded-full bg-gray-200 border-2 border-white flex items-center justify-center text-[10px] font-semibold text-gray-600">
                +{site.assigned_techs.length - 3}
              </div>
            )}
          </div>
        )}
      </div>
    </button>
  );
}

function AreaAccordion({ area }: { area: AreaDashboard }) {
  const [expanded, setExpanded] = useState(true);

  const totalWOs = Object.values(area.priority_counts).reduce((sum, c) => sum + c, 0);
  const hasEscalated = area.escalated_count > 0;
  const hasSafetyFlags = area.safety_flag_count > 0;

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
      {/* Accordion header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center justify-between w-full px-4 py-3 min-h-[56px] hover:bg-gray-50 active:bg-gray-100 transition-colors text-left"
      >
        <div className="flex items-center gap-3 min-w-0">
          {expanded ? (
            <ChevronDown size={18} className="text-gray-500 shrink-0" />
          ) : (
            <ChevronRight size={18} className="text-gray-500 shrink-0" />
          )}
          <span className="font-semibold text-gray-900 truncate">{area.area_name}</span>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {hasSafetyFlags && (
            <span className="inline-flex items-center gap-1 text-xs font-semibold text-red-600 bg-red-50 px-2 py-0.5 rounded-full">
              <AlertTriangle size={12} /> {area.safety_flag_count}
            </span>
          )}
          {hasEscalated && (
            <span className="inline-flex items-center gap-1 text-xs font-semibold text-red-700 bg-red-100 px-2 py-0.5 rounded-full animate-pulse">
              <ArrowUpCircle size={12} /> {area.escalated_count}
            </span>
          )}

          {/* Priority breakdown pills */}
          <div className="flex gap-1 ml-1">
            {(Object.entries(area.priority_counts) as [string, number][])
              .filter(([, count]) => count > 0)
              .sort(([a], [b]) => {
                const order = [WorkOrderPriority.IMMEDIATE, WorkOrderPriority.URGENT, WorkOrderPriority.SCHEDULED, WorkOrderPriority.DEFERRED];
                return order.indexOf(a as WorkOrderPriority) - order.indexOf(b as WorkOrderPriority);
              })
              .map(([priority, count]) => {
                const config = getPriorityConfig(priority as WorkOrderPriority);
                return (
                  <span
                    key={priority}
                    className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${config.bgColor} ${config.textColor}`}
                    title={`${config.label}: ${count}`}
                  >
                    {count}
                  </span>
                );
              })}
          </div>

          <span className="text-xs text-gray-500 ml-1">{totalWOs} total</span>
        </div>
      </button>

      {/* Expanded sites */}
      {expanded && area.sites.length > 0 && (
        <div className="border-t border-gray-100">
          {area.sites.map((site) => (
            <SiteRow key={site.site_id} site={site} />
          ))}
        </div>
      )}

      {expanded && area.sites.length === 0 && (
        <div className="border-t border-gray-100 px-4 py-6 text-center text-sm text-gray-400">
          No sites in this area
        </div>
      )}
    </div>
  );
}

// ------- SkeletonLoader -------

function DashboardSkeleton() {
  return (
    <div className="animate-pulse space-y-6">
      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-[88px] bg-gray-200 rounded-xl" />
        ))}
      </div>
      {/* Area cards */}
      {Array.from({ length: 3 }).map((_, i) => (
        <div key={i} className="h-32 bg-gray-200 rounded-xl" />
      ))}
    </div>
  );
}

// ------- Main Component -------

export default function DashboardPage() {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const { onShift } = useUIStore();
  const pullStartY = useRef<number | null>(null);
  const [isPulling, setIsPulling] = useState(false);

  const {
    data: dashboard,
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ['dashboard', 'overview'],
    queryFn: () => dashboardApi.overview().then((r) => r.data),
    refetchInterval: 30_000,
    staleTime: 15_000,
  });

  // Computed totals
  const totals = dashboard?.areas.reduce(
    (acc, area) => ({
      openWOs: acc.openWOs + Object.values(area.priority_counts).reduce((s, c) => s + c, 0),
      escalated: acc.escalated + area.escalated_count,
      safetyFlags: acc.safetyFlags + area.safety_flag_count,
    }),
    { openWOs: 0, escalated: 0, safetyFlags: 0 }
  ) || { openWOs: 0, escalated: 0, safetyFlags: 0 };

  // My assigned count - sum across all sites' assigned techs that match current user
  const myAssignedCount = dashboard?.areas.reduce((count, area) => {
    return count + area.sites.reduce((siteCount, site) => {
      const isAssigned = site.assigned_techs.some((t) => t.id === user?.id);
      return siteCount + (isAssigned ? site.wo_count : 0);
    }, 0);
  }, 0) || 0;

  // Pull-to-refresh handlers
  const handleTouchStart = useCallback((e: React.TouchEvent) => {
    const scrollTop = (e.currentTarget as HTMLElement).scrollTop;
    if (scrollTop <= 0) {
      pullStartY.current = e.touches[0].clientY;
    }
  }, []);

  const handleTouchMove = useCallback((e: React.TouchEvent) => {
    if (pullStartY.current === null) return;
    const diff = e.touches[0].clientY - pullStartY.current;
    if (diff > 60) {
      setIsPulling(true);
    }
  }, []);

  const handleTouchEnd = useCallback(() => {
    if (isPulling) {
      refetch();
    }
    pullStartY.current = null;
    setIsPulling(false);
  }, [isPulling, refetch]);

  const today = format(new Date(), 'EEEE, MMMM d, yyyy');
  const greeting = user ? `Hello, ${user.name.split(' ')[0]}` : 'Hello';

  return (
    <div
      className="max-w-4xl mx-auto"
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleTouchEnd}
    >
      {/* Pull-to-refresh indicator */}
      {isPulling && (
        <div className="flex items-center justify-center py-3 -mt-2 mb-2">
          <RefreshCw size={18} className="text-navy-600 animate-spin" />
          <span className="ml-2 text-sm text-navy-600 font-medium">Release to refresh</span>
        </div>
      )}

      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-sm text-gray-500 mt-0.5">{today}</p>
          <p className="text-sm text-gray-600 font-medium mt-1">{greeting}</p>
        </div>
        <div className="flex items-center gap-2">
          {isFetching && !isLoading && (
            <Loader2 size={16} className="text-gray-400 animate-spin" />
          )}
          <div className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium ${
            onShift ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-500'
          }`}>
            <span className={`w-2 h-2 rounded-full ${onShift ? 'bg-green-500' : 'bg-gray-400'}`} />
            {onShift ? 'On Shift' : 'Off Shift'}
          </div>
        </div>
      </div>

      {/* Loading */}
      {isLoading && <DashboardSkeleton />}

      {/* Error */}
      {isError && !isLoading && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-center">
          <ShieldAlert size={32} className="text-red-400 mx-auto mb-2" />
          <p className="text-sm text-red-700 font-medium mb-1">Failed to load dashboard</p>
          <p className="text-xs text-red-500 mb-4">{(error as Error)?.message || 'Unknown error'}</p>
          <button
            onClick={() => refetch()}
            className="inline-flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded-lg text-sm font-medium hover:bg-red-700 min-h-[48px] transition-colors"
          >
            <RefreshCw size={16} /> Retry
          </button>
        </div>
      )}

      {/* Dashboard content */}
      {dashboard && !isLoading && (
        <>
          {/* Quick stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
            <StatCard
              label="Open WOs"
              value={totals.openWOs}
              icon={ClipboardList}
              bgColor="bg-blue-50"
              textColor="text-blue-700"
              onClick={() => navigate('/work-orders')}
            />
            <StatCard
              label="Escalated"
              value={totals.escalated}
              icon={ArrowUpCircle}
              bgColor={totals.escalated > 0 ? 'bg-red-50' : 'bg-gray-50'}
              textColor={totals.escalated > 0 ? 'text-red-700' : 'text-gray-400'}
              onClick={() => navigate('/work-orders?tab=escalated')}
            />
            <StatCard
              label="Safety Flags"
              value={totals.safetyFlags}
              icon={AlertTriangle}
              bgColor={totals.safetyFlags > 0 ? 'bg-amber-50' : 'bg-gray-50'}
              textColor={totals.safetyFlags > 0 ? 'text-amber-700' : 'text-gray-400'}
              onClick={() => navigate('/work-orders?tab=safety')}
            />
            <StatCard
              label="My Assigned"
              value={myAssignedCount}
              icon={Clock}
              bgColor="bg-indigo-50"
              textColor="text-indigo-700"
              onClick={() => navigate('/work-orders?tab=mine')}
            />
          </div>

          {/* Area breakdown */}
          <div className="space-y-4">
            <h2 className="text-lg font-semibold text-gray-900">Areas</h2>
            {dashboard.areas.length === 0 ? (
              <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8 text-center">
                <MapPin size={32} className="text-gray-300 mx-auto mb-2" />
                <p className="text-sm text-gray-500">No areas configured yet</p>
              </div>
            ) : (
              dashboard.areas.map((area) => (
                <AreaAccordion key={area.area_id} area={area} />
              ))
            )}
          </div>
        </>
      )}

      {/* Floating Action Button */}
      <button
        onClick={() => navigate('/work-orders/new')}
        className="fixed bottom-24 md:bottom-8 right-6 w-14 h-14 bg-navy-900 hover:bg-navy-800 active:bg-navy-700 text-white rounded-full shadow-lg flex items-center justify-center transition-all hover:scale-105 z-40"
        aria-label="New Work Order"
      >
        <Plus size={24} />
      </button>
    </div>
  );
}
