import { useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  MapPin, ChevronRight, AlertTriangle, QrCode, Download,
  Plus, Wrench, ClipboardList, Info, Loader2, ArrowLeft, ExternalLink,
} from 'lucide-react';
import { sitesApi } from '@/api/sites';
import { SiteType, WorkOrderPriority } from '@/types/enums';
import type { Asset, WorkOrder, Site } from '@/types/api';
import { formatDate } from '@/utils/dateFormat';
import { downloadQrImage } from '@/utils/qrHelpers';
import SafetyFlagBadge from '@/components/SafetyFlagBadge';
import StatusBadge from '@/components/StatusBadge';
import PriorityBadge from '@/components/PriorityBadge';
import HumanReadableNumber from '@/components/HumanReadableNumber';

type TabId = 'assets' | 'work-orders' | 'details';

const siteTypeLabels: Record<string, string> = {
  [SiteType.WELL_SITE]: 'Well Site',
  [SiteType.PLANT]: 'Plant',
  [SiteType.BUILDING]: 'Building',
  [SiteType.COMPRESSOR_STATION]: 'Compressor Station',
  [SiteType.TANK_BATTERY]: 'Tank Battery',
  [SiteType.SEPARATOR]: 'Separator',
  [SiteType.LINE]: 'Line',
  [SiteType.SUITE]: 'Suite',
  [SiteType.APARTMENT]: 'Apartment',
  [SiteType.OTHER]: 'Other',
};

const siteTypeBadgeColor: Record<string, string> = {
  [SiteType.WELL_SITE]: 'bg-emerald-100 text-emerald-800',
  [SiteType.PLANT]: 'bg-blue-100 text-blue-800',
  [SiteType.BUILDING]: 'bg-purple-100 text-purple-800',
  [SiteType.COMPRESSOR_STATION]: 'bg-orange-100 text-orange-800',
  [SiteType.TANK_BATTERY]: 'bg-amber-100 text-amber-800',
  [SiteType.SEPARATOR]: 'bg-cyan-100 text-cyan-800',
  [SiteType.LINE]: 'bg-teal-100 text-teal-800',
  [SiteType.SUITE]: 'bg-indigo-100 text-indigo-800',
  [SiteType.APARTMENT]: 'bg-pink-100 text-pink-800',
  [SiteType.OTHER]: 'bg-gray-100 text-gray-800',
};

// ------- Sub-components -------

function AssetCard({ asset }: { asset: Asset }) {
  const navigate = useNavigate();
  return (
    <button
      onClick={() => navigate(`/assets/${asset.id}`)}
      className="flex items-center justify-between w-full p-4 bg-white rounded-lg border border-gray-200 hover:border-gray-300 hover:shadow-sm active:bg-gray-50 transition-all min-h-[48px] text-left"
    >
      <div className="flex items-center gap-3 min-w-0">
        <div className="w-10 h-10 bg-navy-100 rounded-lg flex items-center justify-center shrink-0">
          <Wrench size={18} className="text-navy-600" />
        </div>
        <div className="min-w-0">
          <p className="text-sm font-semibold text-gray-900 truncate">{asset.name}</p>
          <p className="text-xs text-gray-500 truncate">
            {[asset.manufacturer, asset.model].filter(Boolean).join(' - ') || 'No model info'}
          </p>
        </div>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
          asset.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
        }`}>
          {asset.is_active ? 'Active' : 'Inactive'}
        </span>
        <ChevronRight size={16} className="text-gray-400" />
      </div>
    </button>
  );
}

function WorkOrderCard({ wo }: { wo: WorkOrder }) {
  const navigate = useNavigate();
  return (
    <button
      onClick={() => navigate(`/work-orders/${wo.id}`)}
      className={`w-full p-4 bg-white rounded-lg border text-left transition-all hover:shadow-sm active:bg-gray-50 min-h-[48px] ${
        wo.safety_flag ? 'border-red-300 border-l-4 border-l-red-500' : 'border-gray-200'
      }`}
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-1">
            <HumanReadableNumber number={wo.human_readable_number} size="sm" copyable={false} />
            {wo.safety_flag && <SafetyFlagBadge size="sm" showLabel={false} />}
          </div>
          <p className="text-sm font-medium text-gray-900 truncate">{wo.title}</p>
        </div>
        <StatusBadge status={wo.status} size="sm" />
      </div>
      <div className="flex items-center gap-2">
        <PriorityBadge priority={wo.priority} size="sm" />
        {wo.assignee_name && (
          <span className="text-xs text-gray-500 truncate">{wo.assignee_name}</span>
        )}
      </div>
    </button>
  );
}

function DetailRow({ label, value }: { label: string; value: React.ReactNode }) {
  if (!value) return null;
  return (
    <div className="flex justify-between items-start py-3 border-b border-gray-100 last:border-b-0">
      <span className="text-sm text-gray-500 shrink-0">{label}</span>
      <span className="text-sm font-medium text-gray-900 text-right ml-4">{value}</span>
    </div>
  );
}

function SkeletonCard() {
  return <div className="h-20 bg-gray-200 rounded-lg animate-pulse" />;
}

// ------- Main Component -------

export default function SiteDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<TabId>('assets');

  // Fetch site
  const {
    data: site,
    isLoading: siteLoading,
    isError: siteError,
  } = useQuery({
    queryKey: ['site', id],
    queryFn: () => sitesApi.get(id!).then((r) => r.data),
    enabled: !!id,
  });

  // Fetch assets for this site
  const {
    data: assets,
    isLoading: assetsLoading,
  } = useQuery({
    queryKey: ['site', id, 'assets'],
    queryFn: () => sitesApi.getAssets(id!).then((r) => r.data),
    enabled: !!id && activeTab === 'assets',
  });

  // Fetch work orders for this site
  const {
    data: workOrdersResponse,
    isLoading: wosLoading,
  } = useQuery({
    queryKey: ['site', id, 'work-orders'],
    queryFn: () => sitesApi.getWorkOrderHistory(id!).then((r) => r.data),
    enabled: !!id && activeTab === 'work-orders',
  });

  const handleDownloadQr = async () => {
    if (!id || !site) return;
    try {
      const response = await sitesApi.getQrCode(id);
      downloadQrImage(response.data as Blob, `site-${site.name}-qr.png`);
    } catch {
      // QR download failed silently
    }
  };

  const tabs: { id: TabId; label: string; icon: React.ComponentType<{ size?: number }> }[] = [
    { id: 'assets', label: 'Assets', icon: Wrench },
    { id: 'work-orders', label: 'Work Orders', icon: ClipboardList },
    { id: 'details', label: 'Details', icon: Info },
  ];

  // Full-page loading
  if (siteLoading) {
    return (
      <div className="max-w-3xl mx-auto">
        <div className="animate-pulse space-y-4">
          <div className="h-8 w-48 bg-gray-200 rounded" />
          <div className="h-4 w-32 bg-gray-200 rounded" />
          <div className="h-40 bg-gray-200 rounded-xl" />
          <div className="h-10 bg-gray-200 rounded" />
          <div className="space-y-3">
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
          </div>
        </div>
      </div>
    );
  }

  // Error
  if (siteError || !site) {
    return (
      <div className="max-w-3xl mx-auto text-center py-12">
        <MapPin size={48} className="text-gray-300 mx-auto mb-4" />
        <h2 className="text-lg font-semibold text-gray-900 mb-1">Site not found</h2>
        <p className="text-sm text-gray-500 mb-6">The site you are looking for does not exist or you lack permission to view it.</p>
        <button
          onClick={() => navigate(-1)}
          className="inline-flex items-center gap-2 px-4 py-3 bg-navy-900 text-white rounded-lg text-sm font-medium hover:bg-navy-800 min-h-[48px]"
        >
          <ArrowLeft size={16} /> Go back
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto">
      {/* Back nav */}
      <button
        onClick={() => navigate(-1)}
        className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 mb-4 min-h-[48px]"
      >
        <ArrowLeft size={16} />
        Back
      </button>

      {/* Site header */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-3 flex-wrap mb-2">
              <h1 className="text-xl font-bold text-gray-900">{site.name}</h1>
              <span className={`text-xs px-2.5 py-1 rounded-full font-medium ${
                siteTypeBadgeColor[site.type] || 'bg-gray-100 text-gray-800'
              }`}>
                {siteTypeLabels[site.type] || site.type}
              </span>
            </div>

            {/* Safety flag */}
            {/* Site safety - always visible area for any safety flags from WOs */}
            {workOrdersResponse?.items.some((wo: WorkOrder) => wo.safety_flag) && (
              <div className="flex items-center gap-2 mb-3 p-2 bg-red-50 border border-red-200 rounded-lg">
                <SafetyFlagBadge size="md" />
                <span className="text-sm text-red-700 font-medium">Active safety flags on work orders at this site</span>
              </div>
            )}

            {/* Location */}
            {site.address && (
              <div className="flex items-center gap-2 text-sm text-gray-600 mb-1">
                <MapPin size={14} className="shrink-0" />
                <span>{site.address}</span>
              </div>
            )}

            {/* GPS */}
            {site.gps_lat && site.gps_lng && (
              <div className="flex items-center gap-2 text-xs text-gray-400">
                <ExternalLink size={12} />
                <a
                  href={`https://maps.google.com/?q=${site.gps_lat},${site.gps_lng}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="hover:text-navy-600 underline"
                >
                  {site.gps_lat.toFixed(6)}, {site.gps_lng.toFixed(6)}
                </a>
              </div>
            )}
          </div>

          {/* QR Code actions */}
          <div className="flex flex-col items-center gap-2 shrink-0">
            <div className="w-16 h-16 bg-gray-100 rounded-lg flex items-center justify-center border border-gray-200">
              <QrCode size={28} className="text-gray-400" />
            </div>
            <button
              onClick={handleDownloadQr}
              className="inline-flex items-center gap-1 text-xs text-navy-600 hover:text-navy-800 font-medium min-h-[48px]"
            >
              <Download size={12} /> Download QR
            </button>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-gray-200 mb-6 -mx-1">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 min-h-[48px] transition-colors mx-1 ${
                isActive
                  ? 'border-navy-900 text-navy-900'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              <Icon size={16} />
              {tab.label}
              {tab.id === 'assets' && assets && (
                <span className="text-xs bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded-full">
                  {assets.length}
                </span>
              )}
              {tab.id === 'work-orders' && workOrdersResponse && (
                <span className="text-xs bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded-full">
                  {workOrdersResponse.total}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Tab content: Assets */}
      {activeTab === 'assets' && (
        <div className="space-y-3">
          {assetsLoading ? (
            Array.from({ length: 3 }).map((_, i) => <SkeletonCard key={i} />)
          ) : assets && assets.length > 0 ? (
            assets.map((asset) => <AssetCard key={asset.id} asset={asset} />)
          ) : (
            <div className="bg-white rounded-xl border border-gray-200 p-8 text-center">
              <Wrench size={32} className="text-gray-300 mx-auto mb-2" />
              <p className="text-sm text-gray-500 mb-1">No assets at this site</p>
              <p className="text-xs text-gray-400">Assets added to this site will appear here</p>
            </div>
          )}
        </div>
      )}

      {/* Tab content: Work Orders */}
      {activeTab === 'work-orders' && (
        <div className="space-y-3">
          {wosLoading ? (
            Array.from({ length: 3 }).map((_, i) => <SkeletonCard key={i} />)
          ) : workOrdersResponse && workOrdersResponse.items.length > 0 ? (
            workOrdersResponse.items.map((wo: WorkOrder) => (
              <WorkOrderCard key={wo.id} wo={wo} />
            ))
          ) : (
            <div className="bg-white rounded-xl border border-gray-200 p-8 text-center">
              <ClipboardList size={32} className="text-gray-300 mx-auto mb-2" />
              <p className="text-sm text-gray-500">No work orders for this site</p>
            </div>
          )}
        </div>
      )}

      {/* Tab content: Details */}
      {activeTab === 'details' && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <DetailRow label="Site Name" value={site.name} />
          <DetailRow label="Type" value={siteTypeLabels[site.type] || site.type} />
          <DetailRow label="Address" value={site.address} />
          <DetailRow label="Timezone" value={site.site_timezone} />
          <DetailRow
            label="GPS Coordinates"
            value={
              site.gps_lat && site.gps_lng
                ? `${site.gps_lat.toFixed(6)}, ${site.gps_lng.toFixed(6)}`
                : undefined
            }
          />
          <DetailRow label="QR Token" value={site.qr_code_token} />
          <DetailRow
            label="Status"
            value={
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                site.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
              }`}>
                {site.is_active ? 'Active' : 'Inactive'}
              </span>
            }
          />
          <DetailRow label="Created" value={formatDate(site.created_at)} />
        </div>
      )}

      {/* New WO for this site button */}
      <div className="mt-6 mb-8">
        <button
          onClick={() => navigate(`/work-orders/new?site_id=${site.id}`)}
          className="w-full md:w-auto inline-flex items-center justify-center gap-2 px-6 h-12 bg-navy-900 hover:bg-navy-800 text-white font-semibold rounded-lg transition-colors"
        >
          <Plus size={18} />
          New Work Order for this Site
        </button>
      </div>
    </div>
  );
}
