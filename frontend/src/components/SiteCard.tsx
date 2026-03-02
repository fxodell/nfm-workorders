import { useNavigate } from 'react-router-dom';
import { MapPin, AlertTriangle, ClipboardList } from 'lucide-react';
import type { SiteDashboard } from '@/types/api';
import { SiteType, WorkOrderPriority } from '@/types/enums';

interface Props {
  site: SiteDashboard;
}

const siteTypeLabels: Record<SiteType, string> = {
  [SiteType.WELL_SITE]: 'Well Site',
  [SiteType.PLANT]: 'Plant',
  [SiteType.BUILDING]: 'Building',
  [SiteType.APARTMENT]: 'Apartment',
  [SiteType.LINE]: 'Line',
  [SiteType.SUITE]: 'Suite',
  [SiteType.COMPRESSOR_STATION]: 'Compressor Station',
  [SiteType.TANK_BATTERY]: 'Tank Battery',
  [SiteType.SEPARATOR]: 'Separator',
  [SiteType.OTHER]: 'Other',
};

const siteTypeBgColors: Record<SiteType, string> = {
  [SiteType.WELL_SITE]: 'bg-emerald-100 text-emerald-800',
  [SiteType.PLANT]: 'bg-blue-100 text-blue-800',
  [SiteType.BUILDING]: 'bg-purple-100 text-purple-800',
  [SiteType.APARTMENT]: 'bg-pink-100 text-pink-800',
  [SiteType.LINE]: 'bg-cyan-100 text-cyan-800',
  [SiteType.SUITE]: 'bg-violet-100 text-violet-800',
  [SiteType.COMPRESSOR_STATION]: 'bg-orange-100 text-orange-800',
  [SiteType.TANK_BATTERY]: 'bg-amber-100 text-amber-800',
  [SiteType.SEPARATOR]: 'bg-teal-100 text-teal-800',
  [SiteType.OTHER]: 'bg-gray-100 text-gray-800',
};

const priorityBorderMap: Partial<Record<WorkOrderPriority, string>> = {
  [WorkOrderPriority.IMMEDIATE]: 'border-l-red-600',
  [WorkOrderPriority.URGENT]: 'border-l-orange-600',
  [WorkOrderPriority.SCHEDULED]: 'border-l-yellow-500',
  [WorkOrderPriority.DEFERRED]: 'border-l-gray-400',
};

export default function SiteCard({ site }: Props) {
  const navigate = useNavigate();

  const handleClick = () => {
    navigate(`/sites/${site.site_id}`);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleClick();
    }
  };

  const borderClass = site.highest_priority
    ? priorityBorderMap[site.highest_priority] || 'border-l-gray-300'
    : 'border-l-gray-300';

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      className={`
        bg-white rounded-lg shadow-sm border border-gray-200 border-l-4 ${borderClass}
        hover:shadow-md active:bg-gray-50 transition-all cursor-pointer
        min-h-[48px] p-4 select-none
      `}
      aria-label={`Site ${site.site_name}, ${site.wo_count} open work orders`}
    >
      {/* Header: Site name + Safety flag */}
      <div className="flex items-start justify-between gap-2 mb-2">
        <h3 className="text-sm font-semibold text-gray-900 truncate flex-1">
          {site.site_name}
        </h3>
        <div className="flex items-center gap-2 shrink-0">
          {site.safety_flag && (
            <span className="inline-flex items-center gap-1 text-red-600" title="Safety hazard present">
              <AlertTriangle size={16} className="text-red-600" />
            </span>
          )}
          {site.escalated && (
            <span className="inline-flex items-center px-1.5 py-0.5 bg-red-100 text-red-700 text-xs font-semibold rounded animate-pulse">
              ESC
            </span>
          )}
        </div>
      </div>

      {/* Badges row */}
      <div className="flex flex-wrap items-center gap-1.5 mb-3">
        <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${siteTypeBgColors[site.site_type] || 'bg-gray-100 text-gray-800'}`}>
          {siteTypeLabels[site.site_type] || site.site_type}
        </span>

        {site.wo_count > 0 && (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-100 text-blue-800 text-xs font-medium rounded-full">
            <ClipboardList size={12} />
            {site.wo_count} open
          </span>
        )}
      </div>

      {/* Waiting states */}
      {(site.waiting_on_ops > 0 || site.waiting_on_parts > 0) && (
        <div className="flex flex-wrap gap-1.5 mb-3">
          {site.waiting_on_ops > 0 && (
            <span className="inline-flex items-center px-2 py-0.5 bg-amber-100 text-amber-800 text-xs font-medium rounded">
              {site.waiting_on_ops} waiting on ops
            </span>
          )}
          {site.waiting_on_parts > 0 && (
            <span className="inline-flex items-center px-2 py-0.5 bg-amber-100 text-amber-800 text-xs font-medium rounded">
              {site.waiting_on_parts} waiting on parts
            </span>
          )}
        </div>
      )}

      {/* Assigned techs */}
      {site.assigned_techs && site.assigned_techs.length > 0 && (
        <div className="flex items-center gap-1 mt-2">
          <div className="flex -space-x-2">
            {site.assigned_techs.slice(0, 4).map((tech) => (
              <div
                key={tech.id}
                className="w-7 h-7 rounded-full bg-navy-200 border-2 border-white flex items-center justify-center text-navy-800 text-xs font-semibold"
                title={tech.name}
              >
                {tech.name?.charAt(0).toUpperCase() || '?'}
              </div>
            ))}
            {site.assigned_techs.length > 4 && (
              <div className="w-7 h-7 rounded-full bg-gray-200 border-2 border-white flex items-center justify-center text-gray-600 text-xs font-semibold">
                +{site.assigned_techs.length - 4}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
