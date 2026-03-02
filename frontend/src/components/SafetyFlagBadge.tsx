import { AlertTriangle } from 'lucide-react';

interface Props {
  safetyNotes?: string;
  size?: 'sm' | 'md' | 'lg';
  showLabel?: boolean;
}

export default function SafetyFlagBadge({ safetyNotes, size = 'sm', showLabel = true }: Props) {
  const iconSize = size === 'lg' ? 20 : size === 'md' ? 16 : 14;
  return (
    <span className="inline-flex items-center gap-1 text-red-600 font-semibold" title={safetyNotes || 'Safety hazard flagged'}>
      <AlertTriangle size={iconSize} className="text-red-600" />
      {showLabel && <span className={size === 'sm' ? 'text-xs' : 'text-sm'}>SAFETY</span>}
    </span>
  );
}
