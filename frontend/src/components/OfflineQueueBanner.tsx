import { Cloud, CloudOff, Loader2 } from 'lucide-react';
import { useOfflineQueueStore } from '@/stores/offlineQueueStore';
import { isOnline } from '@/utils/offlineDetect';

export default function OfflineQueueBanner() {
  const { pendingCount, isSyncing, showWarning24h, showWarning48h } = useOfflineQueueStore();
  const online = isOnline();

  if (pendingCount === 0 && online) return null;

  return (
    <div className={`inline-flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium ${
      !online ? 'bg-red-100 text-red-800' :
      showWarning48h ? 'bg-red-100 text-red-800 animate-pulse' :
      showWarning24h ? 'bg-yellow-100 text-yellow-800' :
      isSyncing ? 'bg-blue-100 text-blue-800' :
      'bg-yellow-100 text-yellow-800'
    }`}>
      {!online ? <CloudOff size={16} /> : isSyncing ? <Loader2 size={16} className="animate-spin" /> : <Cloud size={16} />}
      {!online ? 'Offline' :
       isSyncing ? 'Syncing...' :
       showWarning48h ? `${pendingCount} actions unsynced (48h+)` :
       `${pendingCount} pending sync`}
    </div>
  );
}
