import { X, AlertTriangle, Bell } from 'lucide-react';
import { useNotificationStore } from '@/stores/notificationStore';
import { timeAgo } from '@/utils/dateFormat';

export default function NotificationDrawer() {
  const { items, drawerOpen, setDrawerOpen, markAllRead } = useNotificationStore();

  if (!drawerOpen) return null;

  return (
    <>
      <div className="fixed inset-0 bg-black/30 z-40" onClick={() => setDrawerOpen(false)} />
      <div className="fixed right-0 top-0 h-full w-80 bg-white shadow-xl z-50 flex flex-col">
        <div className="flex items-center justify-between p-4 border-b">
          <h2 className="text-lg font-semibold">Notifications</h2>
          <div className="flex items-center gap-2">
            <button onClick={markAllRead} className="text-sm text-navy-600 hover:underline min-h-touch px-2 flex items-center">
              Mark all read
            </button>
            <button onClick={() => setDrawerOpen(false)} className="p-2 hover:bg-gray-100 rounded min-h-touch min-w-touch flex items-center justify-center">
              <X size={20} />
            </button>
          </div>
        </div>
        <div className="flex-1 overflow-auto">
          {items.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-48 text-gray-400">
              <Bell size={32} />
              <p className="mt-2">No notifications</p>
            </div>
          ) : (
            items.map((item) => (
              <div
                key={item.id}
                className={`p-4 border-b hover:bg-gray-50 cursor-pointer ${!item.read ? 'bg-blue-50' : ''}`}
              >
                <div className="flex items-start gap-3">
                  <div className="mt-1">
                    {item.event.data?.safety_flag ? (
                      <AlertTriangle size={16} className="text-red-500" />
                    ) : (
                      <Bell size={16} className="text-gray-400" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate">
                      {String(item.event.data?.human_readable_number || item.event.event)}
                    </p>
                    <p className="text-xs text-gray-500 truncate">
                      {String(item.event.data?.preview || item.event.data?.new_status || '')}
                    </p>
                    <p className="text-xs text-gray-400 mt-1">{timeAgo(item.timestamp)}</p>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </>
  );
}
