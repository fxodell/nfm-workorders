import { useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Wrench, QrCode, Download, Plus, ClipboardList, Info,
  ArrowLeft, MapPin, Calendar, ShieldCheck, AlertTriangle, Loader2,
} from 'lucide-react';
import { assetsApi } from '@/api/assets';
import { sitesApi } from '@/api/sites';
import type { WorkOrder } from '@/types/api';
import { formatDate } from '@/utils/dateFormat';
import { downloadQrImage } from '@/utils/qrHelpers';
import SafetyFlagBadge from '@/components/SafetyFlagBadge';
import StatusBadge from '@/components/StatusBadge';
import PriorityBadge from '@/components/PriorityBadge';
import HumanReadableNumber from '@/components/HumanReadableNumber';

type TabId = 'work-orders' | 'details';

// ------- Sub-components -------

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
        {wo.created_at && (
          <span className="text-xs text-gray-400 ml-auto">{formatDate(wo.created_at)}</span>
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

export default function AssetDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<TabId>('work-orders');

  // Fetch asset
  const {
    data: asset,
    isLoading: assetLoading,
    isError: assetError,
  } = useQuery({
    queryKey: ['asset', id],
    queryFn: () => assetsApi.get(id!).then((r) => r.data),
    enabled: !!id,
  });

  // Fetch parent site for breadcrumb
  const {
    data: site,
  } = useQuery({
    queryKey: ['site', asset?.site_id],
    queryFn: () => sitesApi.get(asset!.site_id).then((r) => r.data),
    enabled: !!asset?.site_id,
  });

  // Fetch work order history for this asset
  const {
    data: workOrdersResponse,
    isLoading: wosLoading,
  } = useQuery({
    queryKey: ['asset', id, 'work-orders'],
    queryFn: () => assetsApi.getWorkOrderHistory(id!).then((r) => r.data),
    enabled: !!id && activeTab === 'work-orders',
  });

  const handleDownloadQr = async () => {
    if (!id || !asset) return;
    try {
      const response = await assetsApi.getQrCode(id);
      downloadQrImage(response.data as Blob, `asset-${asset.name}-qr.png`);
    } catch {
      // QR download failed silently
    }
  };

  // Determine asset status
  const getAssetStatusBadge = () => {
    if (!asset) return null;
    if (asset.is_active) {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-green-100 text-green-800">
          <span className="w-1.5 h-1.5 rounded-full bg-green-500" />
          ACTIVE
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-gray-100 text-gray-600">
        <span className="w-1.5 h-1.5 rounded-full bg-gray-400" />
        INACTIVE
      </span>
    );
  };

  // Check warranty status
  const getWarrantyStatus = () => {
    if (!asset?.warranty_expiry) return null;
    const expiry = new Date(asset.warranty_expiry);
    const now = new Date();
    const isExpired = expiry < now;
    const daysRemaining = Math.ceil((expiry.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));

    if (isExpired) {
      return <span className="text-red-600 font-medium">Expired</span>;
    }
    if (daysRemaining <= 90) {
      return <span className="text-amber-600 font-medium">Expiring soon ({daysRemaining}d)</span>;
    }
    return <span className="text-green-600 font-medium">Valid ({daysRemaining}d remaining)</span>;
  };

  const tabs: { id: TabId; label: string; icon: React.ComponentType<{ size?: number }> }[] = [
    { id: 'work-orders', label: 'Work Orders', icon: ClipboardList },
    { id: 'details', label: 'Details', icon: Info },
  ];

  // Full-page loading
  if (assetLoading) {
    return (
      <div className="max-w-3xl mx-auto">
        <div className="animate-pulse space-y-4">
          <div className="h-8 w-48 bg-gray-200 rounded" />
          <div className="h-4 w-32 bg-gray-200 rounded" />
          <div className="h-48 bg-gray-200 rounded-xl" />
          <div className="h-10 bg-gray-200 rounded" />
          <div className="space-y-3">
            <SkeletonCard />
            <SkeletonCard />
          </div>
        </div>
      </div>
    );
  }

  // Error
  if (assetError || !asset) {
    return (
      <div className="max-w-3xl mx-auto text-center py-12">
        <Wrench size={48} className="text-gray-300 mx-auto mb-4" />
        <h2 className="text-lg font-semibold text-gray-900 mb-1">Asset not found</h2>
        <p className="text-sm text-gray-500 mb-6">The asset you are looking for does not exist or you lack permission to view it.</p>
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

      {/* Asset header */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
            {/* Asset name + status */}
            <div className="flex items-center gap-3 flex-wrap mb-2">
              <h1 className="text-xl font-bold text-gray-900">{asset.name}</h1>
              {getAssetStatusBadge()}
            </div>

            {/* Manufacturer / model */}
            <div className="flex items-center gap-2 flex-wrap mb-3">
              {asset.manufacturer && (
                <span className="text-sm text-gray-600">{asset.manufacturer}</span>
              )}
              {asset.manufacturer && asset.model && (
                <span className="text-gray-300">|</span>
              )}
              {asset.model && (
                <span className="text-sm text-gray-600">{asset.model}</span>
              )}
              {asset.asset_type && (
                <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">
                  {asset.asset_type}
                </span>
              )}
            </div>

            {/* Site link */}
            {site && (
              <Link
                to={`/sites/${site.id}`}
                className="inline-flex items-center gap-2 text-sm text-navy-600 hover:text-navy-800 font-medium mb-3 min-h-[48px]"
              >
                <MapPin size={14} />
                {site.name}
              </Link>
            )}

            {/* Key dates row */}
            <div className="flex items-center gap-4 flex-wrap text-xs text-gray-500">
              {asset.install_date && (
                <div className="flex items-center gap-1">
                  <Calendar size={12} />
                  <span>Installed {formatDate(asset.install_date)}</span>
                </div>
              )}
              {asset.warranty_expiry && (
                <div className="flex items-center gap-1">
                  <ShieldCheck size={12} />
                  <span>Warranty: {getWarrantyStatus()}</span>
                </div>
              )}
            </div>
          </div>

          {/* QR Code */}
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
              {tab.id === 'work-orders' && workOrdersResponse && (
                <span className="text-xs bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded-full">
                  {workOrdersResponse.total}
                </span>
              )}
            </button>
          );
        })}
      </div>

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
              <p className="text-sm text-gray-500">No work order history for this asset</p>
            </div>
          )}
        </div>
      )}

      {/* Tab content: Details */}
      {activeTab === 'details' && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <DetailRow label="Asset Name" value={asset.name} />
          <DetailRow label="Asset Type" value={asset.asset_type} />
          <DetailRow label="Manufacturer" value={asset.manufacturer} />
          <DetailRow label="Model" value={asset.model} />
          <DetailRow label="Serial Number" value={asset.serial_number} />
          <DetailRow label="Install Date" value={asset.install_date ? formatDate(asset.install_date) : undefined} />
          <DetailRow
            label="Warranty Expiry"
            value={
              asset.warranty_expiry ? (
                <span className="flex items-center gap-2">
                  {formatDate(asset.warranty_expiry)}
                  <span className="ml-1">{getWarrantyStatus()}</span>
                </span>
              ) : undefined
            }
          />
          <DetailRow label="QR Token" value={asset.qr_code_token} />
          <DetailRow label="Notes" value={asset.notes} />
          <DetailRow
            label="Status"
            value={getAssetStatusBadge()}
          />
          <DetailRow label="Created" value={formatDate(asset.created_at)} />

          {/* Custom fields */}
          {asset.notes && (
            <div className="mt-4 pt-4 border-t border-gray-200">
              <h3 className="text-sm font-semibold text-gray-700 mb-2">Notes</h3>
              <p className="text-sm text-gray-600 whitespace-pre-wrap">{asset.notes}</p>
            </div>
          )}
        </div>
      )}

      {/* New WO for this asset button */}
      <div className="mt-6 mb-8">
        <button
          onClick={() => navigate(`/work-orders/new?asset_id=${asset.id}&site_id=${asset.site_id}`)}
          className="w-full md:w-auto inline-flex items-center justify-center gap-2 px-6 h-12 bg-navy-900 hover:bg-navy-800 text-white font-semibold rounded-lg transition-colors"
        >
          <Plus size={18} />
          New Work Order for this Asset
        </button>
      </div>
    </div>
  );
}
