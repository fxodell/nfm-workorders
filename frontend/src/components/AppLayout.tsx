import { ReactNode, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Home, ClipboardList, QrCode, Bell, User, Menu, ChevronLeft, LogOut, Settings } from 'lucide-react';
import { useUIStore } from '@/stores/uiStore';
import { useNotificationStore } from '@/stores/notificationStore';
import { useAuthStore } from '@/stores/authStore';
import { useRealtimeChannel } from '@/hooks/useRealtimeChannel';
import ShiftToggle from './ShiftToggle';
import NotificationDrawer from './NotificationDrawer';
import OfflineQueueBanner from './OfflineQueueBanner';
import IOSInstallPrompt from './IOSInstallPrompt';

const navItems = [
  { to: '/', icon: Home, label: 'Home' },
  { to: '/work-orders', icon: ClipboardList, label: 'Work Orders' },
  { to: '/scan', icon: QrCode, label: 'Scan' },
  { to: '/pm', icon: Settings, label: 'PM' },
  { to: '/profile', icon: User, label: 'Profile' },
];

const sidebarItems = [
  { to: '/', icon: Home, label: 'Dashboard' },
  { to: '/work-orders', icon: ClipboardList, label: 'Work Orders' },
  { to: '/scan', icon: QrCode, label: 'QR Scanner' },
  { to: '/pm', icon: Settings, label: 'Preventive Maint.' },
  { to: '/inventory', icon: ClipboardList, label: 'Inventory' },
  { to: '/reports', icon: ClipboardList, label: 'Reports' },
  { to: '/admin', icon: Settings, label: 'Admin' },
];

export default function AppLayout({ children }: { children: ReactNode }) {
  const location = useLocation();
  const { isMobile, sidebarCollapsed, toggleSidebar, setIsMobile } = useUIStore();
  const { unreadCount, setDrawerOpen, drawerOpen } = useNotificationStore();
  const { user, logout } = useAuthStore();

  useRealtimeChannel();

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [setIsMobile]);

  return (
    <div className="flex h-screen bg-gray-50">
      <IOSInstallPrompt />

      {/* Desktop Sidebar */}
      {!isMobile && (
        <aside className={`${sidebarCollapsed ? 'w-16' : 'w-64'} bg-navy-900 text-white flex flex-col transition-all duration-300`}>
          <div className="flex items-center justify-between p-4 border-b border-navy-700">
            {!sidebarCollapsed && <span className="font-bold text-lg">OFMaint</span>}
            <button onClick={toggleSidebar} className="p-2 hover:bg-navy-800 rounded min-h-touch min-w-touch flex items-center justify-center">
              {sidebarCollapsed ? <Menu size={20} /> : <ChevronLeft size={20} />}
            </button>
          </div>
          <nav className="flex-1 py-4">
            {sidebarItems.map(({ to, icon: Icon, label }) => (
              <Link
                key={to} to={to}
                className={`flex items-center gap-3 px-4 py-3 min-h-touch transition-colors ${
                  location.pathname === to ? 'bg-navy-700 border-r-4 border-white' : 'hover:bg-navy-800'
                }`}
              >
                <Icon size={20} />
                {!sidebarCollapsed && <span>{label}</span>}
              </Link>
            ))}
          </nav>
          <div className="p-4 border-t border-navy-700">
            <button onClick={logout} className="flex items-center gap-3 w-full px-2 py-3 hover:bg-navy-800 rounded min-h-touch">
              <LogOut size={20} />
              {!sidebarCollapsed && <span>Logout</span>}
            </button>
          </div>
        </aside>
      )}

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Header */}
        <header className="bg-white border-b border-gray-200 px-4 py-2 flex items-center justify-between h-16 shrink-0">
          <div className="flex items-center gap-3">
            {isMobile && <span className="font-bold text-navy-900 text-lg">OFMaint</span>}
          </div>
          <div className="flex items-center gap-3">
            <OfflineQueueBanner />
            <ShiftToggle />
            <button
              onClick={() => setDrawerOpen(!drawerOpen)}
              className="relative p-3 hover:bg-gray-100 rounded-lg min-h-touch min-w-touch flex items-center justify-center"
            >
              <Bell size={20} />
              {unreadCount > 0 && (
                <span className="absolute -top-1 -right-1 bg-red-500 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center">
                  {unreadCount > 9 ? '9+' : unreadCount}
                </span>
              )}
            </button>
            {user && (
              <Link to="/profile" className="flex items-center gap-2 p-2 hover:bg-gray-100 rounded-lg min-h-touch">
                <div className="w-8 h-8 bg-navy-200 rounded-full flex items-center justify-center text-navy-800 font-semibold text-sm">
                  {user.name?.charAt(0).toUpperCase() || 'U'}
                </div>
                {!isMobile && <span className="text-sm font-medium">{user.name}</span>}
              </Link>
            )}
          </div>
        </header>

        <NotificationDrawer />

        {/* Page Content */}
        <main className="flex-1 overflow-auto p-4 pb-20 md:pb-4">
          {children}
        </main>
      </div>

      {/* Mobile Bottom Nav */}
      {isMobile && (
        <nav className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 flex z-50">
          {navItems.map(({ to, icon: Icon, label }) => (
            <Link
              key={to} to={to}
              className={`flex-1 flex flex-col items-center justify-center py-2 min-h-touch ${
                location.pathname === to ? 'text-navy-900' : 'text-gray-500'
              }`}
            >
              <Icon size={20} />
              <span className="text-xs mt-1">{label}</span>
            </Link>
          ))}
        </nav>
      )}
    </div>
  );
}
