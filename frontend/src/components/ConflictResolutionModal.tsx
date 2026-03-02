import { AlertTriangle } from 'lucide-react';
import type { OfflineQueueEntry } from '@/types/api';

interface Props {
  entry: OfflineQueueEntry;
  serverState: Record<string, unknown>;
  onKeepServer: () => void;
  onKeepLocal: () => void;
  onClose: () => void;
}

export default function ConflictResolutionModal({ entry, serverState, onKeepServer, onKeepLocal, onClose }: Props) {
  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-2xl max-w-lg w-full max-h-[80vh] overflow-auto">
        <div className="p-6">
          <div className="flex items-center gap-3 mb-4">
            <AlertTriangle className="text-yellow-500" size={24} />
            <h2 className="text-lg font-semibold">Sync Conflict</h2>
          </div>
          <p className="text-sm text-gray-600 mb-4">
            This item was modified on the server while you were offline. Choose which version to keep.
          </p>

          <div className="grid grid-cols-2 gap-4 mb-6">
            <div className="border rounded-lg p-3">
              <h3 className="font-medium text-sm mb-2 text-blue-700">Server Version</h3>
              <pre className="text-xs bg-gray-50 p-2 rounded overflow-auto max-h-40">
                {JSON.stringify(serverState, null, 2)}
              </pre>
            </div>
            <div className="border rounded-lg p-3">
              <h3 className="font-medium text-sm mb-2 text-orange-700">Your Version</h3>
              <pre className="text-xs bg-gray-50 p-2 rounded overflow-auto max-h-40">
                {JSON.stringify(entry.payload, null, 2)}
              </pre>
            </div>
          </div>

          <div className="flex gap-3">
            <button onClick={onKeepServer} className="btn-primary flex-1">Keep Server</button>
            <button onClick={onKeepLocal} className="btn-secondary flex-1">Keep Mine</button>
            <button onClick={onClose} className="px-4 py-2 text-gray-500 hover:text-gray-700 min-h-touch">
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
