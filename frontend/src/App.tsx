import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuthStore } from '@/stores/authStore';
import LoginPage from '@/pages/LoginPage';
import DashboardPage from '@/pages/DashboardPage';
import SiteDetailPage from '@/pages/SiteDetailPage';
import AssetDetailPage from '@/pages/AssetDetailPage';
import WorkOrderListPage from '@/pages/WorkOrderListPage';
import NewWorkOrderPage from '@/pages/NewWorkOrderPage';
import QRScannerPage from '@/pages/QRScannerPage';
import PMPage from '@/pages/PMPage';
import InventoryPage from '@/pages/InventoryPage';
import ReportsPage from '@/pages/ReportsPage';
import AdminPage from '@/pages/AdminPage';
import ProfilePage from '@/pages/ProfilePage';
import WorkOrderDetailPage from '@/pages/WorkOrderDetailPage';
import AppLayout from '@/components/AppLayout';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/*"
        element={
          <ProtectedRoute>
            <AppLayout>
              <Routes>
                <Route path="/" element={<DashboardPage />} />
                <Route path="/dashboard" element={<DashboardPage />} />
                <Route path="/sites/:id" element={<SiteDetailPage />} />
                <Route path="/assets/:id" element={<AssetDetailPage />} />
                <Route path="/work-orders" element={<WorkOrderListPage />} />
                <Route path="/work-orders/new" element={<NewWorkOrderPage />} />
                <Route path="/work-orders/:id" element={<WorkOrderDetailPage />} />
                <Route path="/scan" element={<QRScannerPage />} />
                <Route path="/scan/:entityType/:token" element={<QRScannerPage />} />
                <Route path="/pm" element={<PMPage />} />
                <Route path="/inventory" element={<InventoryPage />} />
                <Route path="/reports" element={<ReportsPage />} />
                <Route path="/admin" element={<AdminPage />} />
                <Route path="/profile" element={<ProfilePage />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </AppLayout>
          </ProtectedRoute>
        }
      />
    </Routes>
  );
}
