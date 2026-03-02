import { useState, useCallback, useMemo, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useQuery, useInfiniteQuery } from '@tanstack/react-query';
import {
  Search, Plus, Filter, X, ChevronDown, AlertTriangle,
  ClipboardList, ArrowUpCircle, Loader2, SortDesc,
} from 'lucide-react';
import { workOrderApi, type WorkOrderFilters } from '@/api/workOrders';
import { useAuthStore } from '@/stores/authStore';
import type { WorkOrder, WorkOrderListResponse } from '@/types/api';
import {
  WorkOrderStatus, WorkOrderPriority, WorkOrderType,
} from '@/types/enums';
import { formatDate, timeAgo } from '@/utils/dateFormat';
import { getPriorityConfig } from '@/utils/priority';
import { getStatusConfig } from '@/utils/status';
import StatusBadge from '@/components/StatusBadge';
import PriorityBadge from '@/components/PriorityBadge';
import TypeBadge from '@/components/TypeBadge';
import SafetyFlagBadge from '@/components/SafetyFlagBadge';
import HumanReadableNumber from '@/components/HumanReadableNumber';

type TabId = 'mine' | 'all' | 'escalated' | 'safety';
type SortField = 'created_desc' | 'priority_desc' | 'due_asc' | 'updated_desc';

const PAGE_SIZE = 20;

// ------- Sub-components -------

function WorkOrderCardItem({ wo }: { wo: WorkOrder }) {
  const navigate = useNavigate();

  return (
    <button
      onClick={() => navigate(`/work-orders/${wo.id}`)}
      className={`w-full p-4 bg-white rounded-xl border text-left transition-all hover:shadow-md active:bg-gray-50 min-h-[48px] ${
        wo.safety_flag
          ? 'border-red-300 border-l-4 border-l-red-500'
          : wo.status === WorkOrderStatus.ESCALATED
            ? 'border-red-200 border-l-4 border-l-red-400'
            : 'border-gray-200'
      }`}
    >
      {/* Row 1: Number + Status */}
      <div className="flex items-center justify-between gap-2 mb-1.5">
        <div className="flex items-center gap-2 min-w-0">
          <HumanReadableNumber number={wo.human_readable_number} size="sm" copyable={false} />
          {wo.safety_flag && <SafetyFlagBadge size="sm" showLabel />}
        </div>
        <StatusBadge status={wo.status} size="sm" />
      </div>

      {/* Row 2: Title */}
      <p className="text-sm font-semibold text-gray-900 truncate mb-2">{wo.title}</p>

      {/* Row 3: Priority, Type, meta */}
      <div className="flex items-center gap-2 flex-wrap">
        <PriorityBadge priority={wo.priority} size="sm" />
        <TypeBadge type={wo.type} />
        {wo.site_name && (
          <span className="text-xs text-gray-500 truncate max-w-[120px]">{wo.site_name}</span>
        )}
        <span className="text-xs text-gray-400 ml-auto shrink-0">{timeAgo(wo.updated_at || wo.created_at)}</span>
      </div>

      {/* Row 4: Assignee */}
      {wo.assignee_name && (
        <div className="flex items-center gap-2 mt-2">
          <div className="w-5 h-5 rounded-full bg-navy-200 flex items-center justify-center text-[10px] font-semibold text-navy-800">
            {wo.assignee_name.charAt(0).toUpperCase()}
          </div>
          <span className="text-xs text-gray-500">{wo.assignee_name}</span>
        </div>
      )}
    </button>
  );
}

function SkeletonCard() {
  return (
    <div className="p-4 bg-white rounded-xl border border-gray-200 animate-pulse">
      <div className="flex justify-between mb-2">
        <div className="h-4 w-20 bg-gray-200 rounded" />
        <div className="h-5 w-16 bg-gray-200 rounded-full" />
      </div>
      <div className="h-4 w-3/4 bg-gray-200 rounded mb-3" />
      <div className="flex gap-2">
        <div className="h-5 w-16 bg-gray-200 rounded-full" />
        <div className="h-5 w-14 bg-gray-200 rounded" />
        <div className="h-3 w-12 bg-gray-200 rounded ml-auto" />
      </div>
    </div>
  );
}

function FilterChip({
  label,
  active,
  onToggle,
  count,
}: {
  label: string;
  active: boolean;
  onToggle: () => void;
  count?: number;
}) {
  return (
    <button
      onClick={onToggle}
      className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium min-h-[36px] transition-colors whitespace-nowrap ${
        active
          ? 'bg-navy-900 text-white'
          : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
      }`}
    >
      {label}
      {count !== undefined && count > 0 && (
        <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${
          active ? 'bg-white/20' : 'bg-gray-200'
        }`}>
          {count}
        </span>
      )}
      {active && <X size={12} />}
    </button>
  );
}

function EmptyState({ tab }: { tab: TabId }) {
  const messages: Record<TabId, { title: string; desc: string }> = {
    mine: { title: 'No work orders assigned to you', desc: 'When work orders are assigned to you, they will appear here.' },
    all: { title: 'No work orders found', desc: 'Try adjusting your filters or create a new work order.' },
    escalated: { title: 'No escalated work orders', desc: 'All work orders are within SLA. Great job!' },
    safety: { title: 'No safety-flagged work orders', desc: 'No active safety concerns at this time.' },
  };

  const msg = messages[tab];

  return (
    <div className="flex flex-col items-center justify-center py-16 px-4">
      <div className="w-20 h-20 bg-gray-100 rounded-full flex items-center justify-center mb-4">
        <ClipboardList size={32} className="text-gray-300" />
      </div>
      <p className="text-base font-semibold text-gray-700 mb-1">{msg.title}</p>
      <p className="text-sm text-gray-400 text-center max-w-xs">{msg.desc}</p>
    </div>
  );
}

// ------- Main Component -------

export default function WorkOrderListPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { user } = useAuthStore();

  // Tab state from URL
  const initialTab = (searchParams.get('tab') as TabId) || 'all';
  const [activeTab, setActiveTab] = useState<TabId>(initialTab);

  // Search
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');

  // Filters
  const [statusFilter, setStatusFilter] = useState<WorkOrderStatus | null>(null);
  const [priorityFilter, setPriorityFilter] = useState<WorkOrderPriority | null>(null);
  const [typeFilter, setTypeFilter] = useState<WorkOrderType | null>(null);
  const [safetyFilter, setSafetyFilter] = useState(false);
  const [showFilters, setShowFilters] = useState(false);

  // Sort
  const [sortField, setSortField] = useState<SortField>('created_desc');
  const [showSortMenu, setShowSortMenu] = useState(false);

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(searchQuery), 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Sync tab to URL
  useEffect(() => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set('tab', activeTab);
      return next;
    }, { replace: true });
  }, [activeTab, setSearchParams]);

  // Build filters for API
  const buildFilters = useCallback(
    (page: number): WorkOrderFilters => {
      const filters: WorkOrderFilters = {
        page,
        per_page: PAGE_SIZE,
      };

      if (debouncedSearch) filters.search = debouncedSearch;
      if (statusFilter) filters.status = statusFilter;
      if (priorityFilter) filters.priority = priorityFilter;
      if (typeFilter) filters.type = typeFilter;
      if (safetyFilter) filters.safety_flag = true;

      // Tab-specific filters
      switch (activeTab) {
        case 'mine':
          if (user) filters.assigned_to = user.id;
          break;
        case 'escalated':
          filters.status = WorkOrderStatus.ESCALATED;
          break;
        case 'safety':
          filters.safety_flag = true;
          break;
        case 'all':
        default:
          break;
      }

      return filters;
    },
    [debouncedSearch, statusFilter, priorityFilter, typeFilter, safetyFilter, activeTab, user]
  );

  // Infinite query for work orders
  const {
    data,
    isLoading,
    isFetchingNextPage,
    hasNextPage,
    fetchNextPage,
    isError,
    refetch,
  } = useInfiniteQuery({
    queryKey: ['workOrders', activeTab, debouncedSearch, statusFilter, priorityFilter, typeFilter, safetyFilter, sortField],
    queryFn: ({ pageParam = 1 }) =>
      workOrderApi.list(buildFilters(pageParam as number)).then((r) => r.data),
    getNextPageParam: (lastPage: WorkOrderListResponse) => {
      const nextPage = lastPage.page + 1;
      const totalPages = Math.ceil(lastPage.total / lastPage.per_page);
      return nextPage <= totalPages ? nextPage : undefined;
    },
    initialPageParam: 1,
    staleTime: 15_000,
  });

  // Flatten pages into single list
  const workOrders = useMemo(() => {
    if (!data?.pages) return [];
    const items = data.pages.flatMap((page) => page.items);

    // Client-side sort (API may also sort, but we ensure order here)
    return [...items].sort((a, b) => {
      switch (sortField) {
        case 'priority_desc': {
          const order = [WorkOrderPriority.IMMEDIATE, WorkOrderPriority.URGENT, WorkOrderPriority.SCHEDULED, WorkOrderPriority.DEFERRED];
          return order.indexOf(a.priority) - order.indexOf(b.priority);
        }
        case 'due_asc':
          if (!a.due_at) return 1;
          if (!b.due_at) return -1;
          return new Date(a.due_at).getTime() - new Date(b.due_at).getTime();
        case 'updated_desc':
          return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime();
        case 'created_desc':
        default:
          return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
      }
    });
  }, [data, sortField]);

  const totalCount = data?.pages[0]?.total ?? 0;

  const handleClearFilters = () => {
    setStatusFilter(null);
    setPriorityFilter(null);
    setTypeFilter(null);
    setSafetyFilter(false);
    setSearchQuery('');
  };

  const hasActiveFilters = statusFilter || priorityFilter || typeFilter || safetyFilter || debouncedSearch;

  const sortOptions: { value: SortField; label: string }[] = [
    { value: 'created_desc', label: 'Newest first' },
    { value: 'priority_desc', label: 'Highest priority' },
    { value: 'due_asc', label: 'Due soonest' },
    { value: 'updated_desc', label: 'Recently updated' },
  ];

  const tabs: { id: TabId; label: string; icon?: React.ComponentType<{ size?: number; className?: string }> }[] = [
    { id: 'mine', label: 'My WOs' },
    { id: 'all', label: 'All WOs' },
    { id: 'escalated', label: 'Escalated', icon: ArrowUpCircle },
    { id: 'safety', label: 'Safety', icon: AlertTriangle },
  ];

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold text-gray-900">Work Orders</h1>
        {totalCount > 0 && (
          <span className="text-sm text-gray-500">{totalCount} total</span>
        )}
      </div>

      {/* Search bar */}
      <div className="relative mb-4">
        <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
        <input
          type="text"
          placeholder="Search work orders..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full h-12 pl-10 pr-20 bg-white border border-gray-200 rounded-xl text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-navy-500 focus:border-transparent"
        />
        <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="p-2 text-gray-400 hover:text-gray-600 min-w-[44px] min-h-[44px] flex items-center justify-center"
            >
              <X size={16} />
            </button>
          )}
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`p-2 rounded-lg min-w-[44px] min-h-[44px] flex items-center justify-center transition-colors ${
              showFilters || hasActiveFilters ? 'bg-navy-100 text-navy-700' : 'text-gray-400 hover:text-gray-600'
            }`}
          >
            <Filter size={18} />
          </button>
        </div>
      </div>

      {/* Tab filters */}
      <div className="flex gap-1 mb-4 overflow-x-auto pb-1 -mx-1 px-1">
        {tabs.map((tab) => {
          const isActive = activeTab === tab.id;
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`inline-flex items-center gap-1.5 px-4 py-2.5 rounded-lg text-sm font-medium min-h-[48px] whitespace-nowrap transition-colors ${
                isActive
                  ? 'bg-navy-900 text-white'
                  : 'bg-white text-gray-600 border border-gray-200 hover:bg-gray-50'
              }`}
            >
              {Icon && <Icon size={14} className={isActive ? 'text-white' : tab.id === 'escalated' ? 'text-red-500' : 'text-amber-500'} />}
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Filter chips panel */}
      {showFilters && (
        <div className="bg-white rounded-xl border border-gray-200 p-4 mb-4 space-y-3">
          {/* Status filters */}
          <div>
            <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 block">Status</span>
            <div className="flex flex-wrap gap-2">
              {Object.values(WorkOrderStatus).map((status) => {
                const config = getStatusConfig(status);
                return (
                  <FilterChip
                    key={status}
                    label={config.label}
                    active={statusFilter === status}
                    onToggle={() => setStatusFilter(statusFilter === status ? null : status)}
                  />
                );
              })}
            </div>
          </div>

          {/* Priority filters */}
          <div>
            <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 block">Priority</span>
            <div className="flex flex-wrap gap-2">
              {Object.values(WorkOrderPriority).map((priority) => {
                const config = getPriorityConfig(priority);
                return (
                  <FilterChip
                    key={priority}
                    label={config.label}
                    active={priorityFilter === priority}
                    onToggle={() => setPriorityFilter(priorityFilter === priority ? null : priority)}
                  />
                );
              })}
            </div>
          </div>

          {/* Type filters */}
          <div>
            <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 block">Type</span>
            <div className="flex flex-wrap gap-2">
              {Object.values(WorkOrderType).map((type) => (
                <FilterChip
                  key={type}
                  label={type}
                  active={typeFilter === type}
                  onToggle={() => setTypeFilter(typeFilter === type ? null : type)}
                />
              ))}
            </div>
          </div>

          {/* Safety flag */}
          <div>
            <FilterChip
              label="Safety Flagged Only"
              active={safetyFilter}
              onToggle={() => setSafetyFilter(!safetyFilter)}
            />
          </div>

          {/* Clear all */}
          {hasActiveFilters && (
            <button
              onClick={handleClearFilters}
              className="text-sm text-navy-600 hover:text-navy-800 font-medium min-h-[48px]"
            >
              Clear all filters
            </button>
          )}
        </div>
      )}

      {/* Sort dropdown */}
      <div className="flex items-center justify-between mb-4">
        {hasActiveFilters && (
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <span>Filtered</span>
            <button onClick={handleClearFilters} className="text-navy-600 hover:underline min-h-[48px] flex items-center">
              Clear
            </button>
          </div>
        )}
        <div className="relative ml-auto">
          <button
            onClick={() => setShowSortMenu(!showSortMenu)}
            className="inline-flex items-center gap-1.5 px-3 py-2 text-sm text-gray-600 hover:text-gray-900 bg-white border border-gray-200 rounded-lg min-h-[48px]"
          >
            <SortDesc size={14} />
            {sortOptions.find((o) => o.value === sortField)?.label}
            <ChevronDown size={14} />
          </button>
          {showSortMenu && (
            <>
              <div className="fixed inset-0 z-10" onClick={() => setShowSortMenu(false)} />
              <div className="absolute right-0 top-full mt-1 w-48 bg-white border border-gray-200 rounded-lg shadow-lg z-20">
                {sortOptions.map((option) => (
                  <button
                    key={option.value}
                    onClick={() => {
                      setSortField(option.value);
                      setShowSortMenu(false);
                    }}
                    className={`w-full text-left px-4 py-3 text-sm min-h-[48px] transition-colors ${
                      sortField === option.value
                        ? 'bg-navy-50 text-navy-900 font-medium'
                        : 'text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Loading skeleton */}
      {isLoading && (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      )}

      {/* Error state */}
      {isError && !isLoading && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-center">
          <p className="text-sm text-red-700 font-medium mb-3">Failed to load work orders</p>
          <button
            onClick={() => refetch()}
            className="inline-flex items-center gap-2 px-4 py-2.5 bg-red-600 text-white rounded-lg text-sm font-medium hover:bg-red-700 min-h-[48px]"
          >
            Retry
          </button>
        </div>
      )}

      {/* Work order list */}
      {!isLoading && !isError && (
        <>
          {workOrders.length === 0 ? (
            <EmptyState tab={activeTab} />
          ) : (
            <div className="space-y-3">
              {workOrders.map((wo) => (
                <WorkOrderCardItem key={wo.id} wo={wo} />
              ))}

              {/* Load more / infinite scroll trigger */}
              {hasNextPage && (
                <div className="flex justify-center py-4">
                  <button
                    onClick={() => fetchNextPage()}
                    disabled={isFetchingNextPage}
                    className="inline-flex items-center gap-2 px-6 py-3 bg-white border border-gray-200 rounded-lg text-sm font-medium text-gray-600 hover:bg-gray-50 min-h-[48px] transition-colors"
                  >
                    {isFetchingNextPage ? (
                      <>
                        <Loader2 size={16} className="animate-spin" />
                        Loading...
                      </>
                    ) : (
                      'Load more'
                    )}
                  </button>
                </div>
              )}

              {!hasNextPage && workOrders.length > 0 && (
                <p className="text-center text-xs text-gray-400 py-4">
                  All {totalCount} work orders loaded
                </p>
              )}
            </div>
          )}
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
