import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Building2, Users, FileText, Search, Plus, X, ChevronDown,
  ChevronRight, Shield, Loader2, AlertTriangle, Save,
  Lock, ToggleLeft, ToggleRight, ArrowLeft, Eye, EyeOff,
  Calendar, User as UserIcon,
} from 'lucide-react';
import { format, parseISO } from 'date-fns';
import { adminApi } from '@/api/admin';
import apiClient from '@/api/client';
import { useAuthStore } from '@/stores/authStore';
import type { Organization, OrgConfig, AuditLog, User } from '@/types/api';
import { UserRole, Permission, WorkOrderPriority } from '@/types/enums';

type TabKey = 'org' | 'users' | 'audit';

const roleColors: Record<UserRole, string> = {
  [UserRole.SUPER_ADMIN]: 'bg-purple-100 text-purple-800',
  [UserRole.ADMIN]: 'bg-red-100 text-red-800',
  [UserRole.SUPERVISOR]: 'bg-blue-100 text-blue-800',
  [UserRole.OPERATOR]: 'bg-green-100 text-green-800',
  [UserRole.TECHNICIAN]: 'bg-yellow-100 text-yellow-800',
  [UserRole.READ_ONLY]: 'bg-gray-100 text-gray-600',
  [UserRole.COST_ANALYST]: 'bg-indigo-100 text-indigo-800',
};

export default function AdminPage() {
  const { user: currentUser } = useAuthStore();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<TabKey>('org');

  // Authorization check
  const isAdmin =
    currentUser?.role === UserRole.ADMIN || currentUser?.role === UserRole.SUPER_ADMIN;

  if (!isAdmin) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center">
          <Shield size={32} className="text-red-600" />
        </div>
        <h1 className="text-xl font-bold text-gray-900">Unauthorized</h1>
        <p className="text-gray-500 text-center max-w-sm">
          You do not have permission to access admin settings. Contact your organization
          administrator for access.
        </p>
      </div>
    );
  }

  const tabs: { key: TabKey; label: string; icon: React.ElementType }[] = [
    { key: 'org', label: 'Organization', icon: Building2 },
    { key: 'users', label: 'Users', icon: Users },
    { key: 'audit', label: 'Audit Log', icon: FileText },
  ];

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-gray-900">Admin Settings</h1>

      {/* Tabs */}
      <div className="flex border-b border-gray-200">
        {tabs.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors min-h-[48px] ${
              activeTab === key
                ? 'border-navy-900 text-navy-900'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            <Icon size={16} />
            {label}
          </button>
        ))}
      </div>

      {activeTab === 'org' && <OrgTab />}
      {activeTab === 'users' && <UsersTab />}
      {activeTab === 'audit' && <AuditLogTab />}
    </div>
  );
}

// ── Organization Tab ────────────────────────────────────────────────────────

function OrgTab() {
  const queryClient = useQueryClient();

  const { data: org, isLoading: orgLoading } = useQuery({
    queryKey: ['admin-org'],
    queryFn: async () => {
      const res = await adminApi.getOrg();
      return res.data;
    },
  });

  const { data: orgConfig, isLoading: configLoading } = useQuery({
    queryKey: ['admin-org-config'],
    queryFn: async () => {
      const res = await adminApi.getOrgConfig();
      return res.data;
    },
  });

  const [orgName, setOrgName] = useState('');
  const [slaConfig, setSlaConfig] = useState<OrgConfig['sla'] | null>(null);
  const [editingConfig, setEditingConfig] = useState(false);

  // Sync state when data loads
  useMemo(() => {
    if (org && !orgName) setOrgName(org.name);
    if (orgConfig && !slaConfig) setSlaConfig(orgConfig.sla);
  }, [org, orgConfig]);

  const updateOrgMutation = useMutation({
    mutationFn: (data: Partial<Organization>) => adminApi.updateOrg(data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin-org'] }),
  });

  const updateConfigMutation = useMutation({
    mutationFn: (config: OrgConfig) => adminApi.updateOrgConfig(config),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-org-config'] });
      setEditingConfig(false);
    },
  });

  if (orgLoading || configLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 size={32} className="animate-spin text-navy-600" />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-2xl">
      {/* Org Name */}
      <div className="bg-white rounded-lg border border-gray-200 p-6 space-y-4">
        <h2 className="text-lg font-semibold text-gray-900">Organization Details</h2>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Organization Name</label>
          <div className="flex gap-3">
            <input
              type="text"
              value={orgName}
              onChange={(e) => setOrgName(e.target.value)}
              className="flex-1 px-3 py-2.5 border border-gray-300 rounded-lg text-sm min-h-[48px] focus:ring-2 focus:ring-navy-500 focus:border-navy-500"
            />
            <button
              onClick={() => updateOrgMutation.mutate({ name: orgName })}
              disabled={orgName === org?.name || updateOrgMutation.isPending}
              className="px-4 py-2.5 bg-navy-900 text-white rounded-lg font-medium min-h-[48px] disabled:opacity-50 flex items-center gap-2"
            >
              <Save size={16} />
              Save
            </button>
          </div>
        </div>
        {org && (
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-gray-500">Slug:</span>{' '}
              <span className="font-medium">{org.slug}</span>
            </div>
            <div>
              <span className="text-gray-500">Currency:</span>{' '}
              <span className="font-medium">{org.currency_code}</span>
            </div>
            <div>
              <span className="text-gray-500">Timezone:</span>{' '}
              <span className="font-medium">{orgConfig?.timezone}</span>
            </div>
            <div>
              <span className="text-gray-500">Escalation:</span>{' '}
              <span className="font-medium">{orgConfig?.escalation_enabled ? 'Enabled' : 'Disabled'}</span>
            </div>
          </div>
        )}
      </div>

      {/* SLA Configuration */}
      <div className="bg-white rounded-lg border border-gray-200 p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">SLA Configuration</h2>
          <button
            onClick={() => setEditingConfig(!editingConfig)}
            className="text-sm font-medium text-navy-600 min-h-[48px] px-3"
          >
            {editingConfig ? 'Cancel' : 'Edit'}
          </button>
        </div>

        {slaConfig && (
          <div className="space-y-4">
            {Object.entries(slaConfig).map(([priority, config]) => (
              <div
                key={priority}
                className="border border-gray-200 rounded-lg p-4"
              >
                <h3 className="font-medium text-gray-900 mb-3">{priority}</h3>
                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">Ack (minutes)</label>
                    {editingConfig ? (
                      <input
                        type="number"
                        min={1}
                        value={config.ack_minutes}
                        onChange={(e) => {
                          const updated = { ...slaConfig };
                          updated[priority] = { ...config, ack_minutes: parseInt(e.target.value) || 0 };
                          setSlaConfig(updated);
                        }}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm min-h-[48px]"
                      />
                    ) : (
                      <div className="text-sm font-medium">{config.ack_minutes}m</div>
                    )}
                  </div>
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">First Update (min)</label>
                    {editingConfig ? (
                      <input
                        type="number"
                        min={1}
                        value={config.first_update_minutes}
                        onChange={(e) => {
                          const updated = { ...slaConfig };
                          updated[priority] = { ...config, first_update_minutes: parseInt(e.target.value) || 0 };
                          setSlaConfig(updated);
                        }}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm min-h-[48px]"
                      />
                    ) : (
                      <div className="text-sm font-medium">{config.first_update_minutes}m</div>
                    )}
                  </div>
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">Resolve (hours)</label>
                    {editingConfig ? (
                      <input
                        type="number"
                        min={1}
                        value={config.resolve_hours}
                        onChange={(e) => {
                          const updated = { ...slaConfig };
                          updated[priority] = { ...config, resolve_hours: parseInt(e.target.value) || 0 };
                          setSlaConfig(updated);
                        }}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm min-h-[48px]"
                      />
                    ) : (
                      <div className="text-sm font-medium">{config.resolve_hours}h</div>
                    )}
                  </div>
                </div>
              </div>
            ))}

            {editingConfig && (
              <button
                onClick={() => {
                  if (orgConfig && slaConfig) {
                    updateConfigMutation.mutate({ ...orgConfig, sla: slaConfig });
                  }
                }}
                disabled={updateConfigMutation.isPending}
                className="w-full px-4 py-2.5 bg-navy-900 text-white rounded-lg font-medium min-h-[48px] disabled:opacity-50 flex items-center justify-center gap-2"
              >
                <Save size={16} />
                {updateConfigMutation.isPending ? 'Saving...' : 'Save SLA Configuration'}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Users Tab ───────────────────────────────────────────────────────────────

function UsersTab() {
  const queryClient = useQueryClient();
  const [searchQuery, setSearchQuery] = useState('');
  const [showCreateUser, setShowCreateUser] = useState(false);
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null);

  const { data: usersData, isLoading } = useQuery({
    queryKey: ['admin-users', searchQuery],
    queryFn: async () => {
      const res = await apiClient.get<{ items: User[]; total: number }>('/admin/users', {
        params: { search: searchQuery || undefined, per_page: 100 },
      });
      return res.data;
    },
  });

  const users = usersData?.items || [];
  const selectedUser = users.find((u) => u.id === selectedUserId);

  if (selectedUser) {
    return (
      <UserDetailView
        user={selectedUser}
        onBack={() => setSelectedUserId(null)}
      />
    );
  }

  return (
    <div className="space-y-4">
      {/* Search + Add */}
      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Search users..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-4 py-2.5 border border-gray-300 rounded-lg text-sm min-h-[48px] focus:ring-2 focus:ring-navy-500 focus:border-navy-500"
          />
        </div>
        <button
          onClick={() => setShowCreateUser(true)}
          className="flex items-center gap-2 px-4 py-2.5 bg-navy-900 text-white rounded-lg font-medium min-h-[48px]"
        >
          <Plus size={18} />
          Add User
        </button>
      </div>

      {/* Users list */}
      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 size={32} className="animate-spin text-navy-600" />
        </div>
      )}

      {!isLoading && users.length === 0 && (
        <div className="text-center py-12">
          <Users size={48} className="mx-auto text-gray-300 mb-3" />
          <p className="text-gray-500">No users found</p>
        </div>
      )}

      <div className="space-y-2">
        {users.map((user) => (
          <button
            key={user.id}
            onClick={() => setSelectedUserId(user.id)}
            className="w-full text-left bg-white rounded-lg border border-gray-200 p-4 hover:shadow-md active:bg-gray-50 transition-all min-h-[48px]"
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-navy-100 rounded-full flex items-center justify-center text-navy-800 font-semibold shrink-0">
                {user.name?.charAt(0).toUpperCase() || 'U'}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-gray-900 truncate">{user.name}</span>
                  <span className={`px-2 py-0.5 text-xs rounded-full font-medium ${roleColors[user.role] || 'bg-gray-100'}`}>
                    {user.role}
                  </span>
                  {!user.is_active && (
                    <span className="px-2 py-0.5 bg-red-100 text-red-600 text-xs rounded-full font-medium">
                      Inactive
                    </span>
                  )}
                </div>
                <div className="text-sm text-gray-500 truncate">{user.email}</div>
              </div>
              <ChevronRight size={16} className="text-gray-400 shrink-0" />
            </div>
          </button>
        ))}
      </div>

      {/* Create User Modal */}
      {showCreateUser && (
        <CreateUserModal onClose={() => setShowCreateUser(false)} />
      )}
    </div>
  );
}

// ── User Detail View ────────────────────────────────────────────────────────

function UserDetailView({ user, onBack }: { user: User; onBack: () => void }) {
  const queryClient = useQueryClient();
  const [role, setRole] = useState<UserRole>(user.role);
  const [isActive, setIsActive] = useState(user.is_active);
  const [permissions, setPermissions] = useState<Record<string, boolean>>({});

  const updateMutation = useMutation({
    mutationFn: (data: Partial<User>) =>
      apiClient.patch(`/admin/users/${user.id}`, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin-users'] }),
  });

  const resetPasswordMutation = useMutation({
    mutationFn: () =>
      apiClient.post(`/admin/users/${user.id}/reset-password`),
  });

  const togglePermission = (perm: string) => {
    setPermissions((prev) => ({ ...prev, [perm]: !prev[perm] }));
  };

  const handleSave = () => {
    updateMutation.mutate({ role, is_active: isActive });
  };

  return (
    <div className="space-y-4 max-w-2xl">
      <div className="flex items-center gap-3">
        <button
          onClick={onBack}
          className="p-3 hover:bg-gray-100 rounded-lg min-h-[48px] min-w-[48px] flex items-center justify-center"
          aria-label="Back to users"
        >
          <ArrowLeft size={20} />
        </button>
        <h2 className="text-lg font-semibold text-gray-900">User Details</h2>
      </div>

      {/* User info */}
      <div className="bg-white rounded-lg border border-gray-200 p-6 space-y-4">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 bg-navy-100 rounded-full flex items-center justify-center text-navy-800 font-bold text-xl">
            {user.name?.charAt(0).toUpperCase() || 'U'}
          </div>
          <div>
            <h3 className="text-lg font-semibold text-gray-900">{user.name}</h3>
            <div className="text-sm text-gray-500">{user.email}</div>
            {user.phone && <div className="text-sm text-gray-500">{user.phone}</div>}
          </div>
        </div>

        {/* Role */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Role</label>
          <select
            value={role}
            onChange={(e) => setRole(e.target.value as UserRole)}
            className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm min-h-[48px] bg-white"
          >
            {Object.values(UserRole).map((r) => (
              <option key={r} value={r}>{r}</option>
            ))}
          </select>
        </div>

        {/* Active toggle */}
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-gray-700">Active</span>
          <button
            onClick={() => setIsActive(!isActive)}
            className="min-h-[48px] min-w-[48px] flex items-center justify-center"
          >
            {isActive ? (
              <ToggleRight size={28} className="text-green-600" />
            ) : (
              <ToggleLeft size={28} className="text-gray-400" />
            )}
          </button>
        </div>

        {/* Permissions */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Permissions</label>
          <div className="space-y-2">
            {Object.values(Permission).map((perm) => (
              <label
                key={perm}
                className="flex items-center gap-3 p-2 rounded-lg hover:bg-gray-50 cursor-pointer min-h-[48px]"
              >
                <input
                  type="checkbox"
                  checked={permissions[perm] ?? false}
                  onChange={() => togglePermission(perm)}
                  className="w-5 h-5 text-navy-600 rounded border-gray-300 focus:ring-navy-500"
                />
                <span className="text-sm text-gray-700">
                  {perm.replace(/^CAN_/, '').replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase())}
                </span>
              </label>
            ))}
          </div>
        </div>

        {/* Actions */}
        <div className="flex flex-wrap gap-3 pt-4 border-t border-gray-200">
          <button
            onClick={handleSave}
            disabled={updateMutation.isPending}
            className="flex-1 px-4 py-2.5 bg-navy-900 text-white rounded-lg font-medium min-h-[48px] disabled:opacity-50 flex items-center justify-center gap-2"
          >
            <Save size={16} />
            {updateMutation.isPending ? 'Saving...' : 'Save Changes'}
          </button>
          <button
            onClick={() => resetPasswordMutation.mutate()}
            disabled={resetPasswordMutation.isPending}
            className="px-4 py-2.5 border border-gray-300 rounded-lg font-medium text-gray-700 min-h-[48px] flex items-center gap-2"
          >
            <Lock size={16} />
            {resetPasswordMutation.isPending ? 'Sending...' : 'Reset Password'}
          </button>
        </div>

        {resetPasswordMutation.isSuccess && (
          <div className="bg-green-50 border border-green-200 rounded-lg p-3 text-green-700 text-sm">
            Password reset email sent successfully.
          </div>
        )}

        {/* Meta info */}
        <div className="text-xs text-gray-400 space-y-1 pt-2 border-t border-gray-100">
          <div>MFA: {user.mfa_enabled ? 'Enabled' : 'Disabled'}</div>
          {user.last_login_at && <div>Last login: {format(parseISO(user.last_login_at), 'MMM d, yyyy h:mm a')}</div>}
          <div>Created: {format(parseISO(user.created_at), 'MMM d, yyyy')}</div>
        </div>
      </div>
    </div>
  );
}

// ── Create User Modal ───────────────────────────────────────────────────────

function CreateUserModal({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    name: '',
    email: '',
    password: '',
    role: UserRole.TECHNICIAN as UserRole,
    phone: '',
  });
  const [showPassword, setShowPassword] = useState(false);

  const updateField = (key: string, value: string) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const createMutation = useMutation({
    mutationFn: () =>
      apiClient.post('/admin/users', {
        name: form.name,
        email: form.email,
        password: form.password,
        role: form.role,
        phone: form.phone || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] });
      onClose();
    },
  });

  return (
    <div className="fixed inset-0 bg-black/50 flex items-end md:items-center justify-center z-50">
      <div className="bg-white rounded-t-2xl md:rounded-xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between z-10">
          <h2 className="text-lg font-semibold text-gray-900">Create User</h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg min-h-[48px] min-w-[48px] flex items-center justify-center"
          >
            <X size={20} />
          </button>
        </div>

        <div className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Full Name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => updateField('name', e.target.value)}
              placeholder="John Smith"
              className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm min-h-[48px] focus:ring-2 focus:ring-navy-500 focus:border-navy-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Email <span className="text-red-500">*</span>
            </label>
            <input
              type="email"
              value={form.email}
              onChange={(e) => updateField('email', e.target.value)}
              placeholder="john@example.com"
              className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm min-h-[48px] focus:ring-2 focus:ring-navy-500 focus:border-navy-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Password <span className="text-red-500">*</span>
            </label>
            <div className="relative">
              <input
                type={showPassword ? 'text' : 'password'}
                value={form.password}
                onChange={(e) => updateField('password', e.target.value)}
                placeholder="Minimum 8 characters"
                className="w-full px-3 py-2.5 pr-12 border border-gray-300 rounded-lg text-sm min-h-[48px] focus:ring-2 focus:ring-navy-500 focus:border-navy-500"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-1 top-1/2 -translate-y-1/2 p-2 min-h-[48px] min-w-[48px] flex items-center justify-center"
              >
                {showPassword ? <EyeOff size={16} className="text-gray-400" /> : <Eye size={16} className="text-gray-400" />}
              </button>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Role</label>
            <select
              value={form.role}
              onChange={(e) => setForm((prev) => ({ ...prev, role: e.target.value as UserRole }))}
              className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm min-h-[48px] bg-white"
            >
              {Object.values(UserRole).map((r) => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Phone</label>
            <input
              type="tel"
              value={form.phone}
              onChange={(e) => updateField('phone', e.target.value)}
              placeholder="+1 (555) 123-4567"
              className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm min-h-[48px] focus:ring-2 focus:ring-navy-500 focus:border-navy-500"
            />
          </div>

          {createMutation.isError && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-red-700 text-sm">
              Failed to create user. Please check the details and try again.
            </div>
          )}
        </div>

        <div className="sticky bottom-0 bg-white border-t border-gray-200 px-6 py-4 flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2.5 border border-gray-300 rounded-lg font-medium text-gray-700 min-h-[48px]"
          >
            Cancel
          </button>
          <button
            onClick={() => createMutation.mutate()}
            disabled={!form.name.trim() || !form.email.trim() || !form.password.trim() || createMutation.isPending}
            className="flex-1 px-4 py-2.5 bg-navy-900 text-white rounded-lg font-medium min-h-[48px] disabled:opacity-50"
          >
            {createMutation.isPending ? 'Creating...' : 'Create User'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Audit Log Tab ───────────────────────────────────────────────────────────

function AuditLogTab() {
  const [page, setPage] = useState(1);
  const [entityTypeFilter, setEntityTypeFilter] = useState('');
  const [actionFilter, setActionFilter] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['audit-log', page, entityTypeFilter, actionFilter, dateFrom, dateTo],
    queryFn: async () => {
      const params: Record<string, unknown> = { page, per_page: 25 };
      if (entityTypeFilter) params.entity_type = entityTypeFilter;
      if (actionFilter) params.action = actionFilter;
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo) params.date_to = dateTo;
      const res = await adminApi.getAuditLog(params);
      return res.data;
    },
  });

  const entries = data?.items || [];
  const total = data?.total || 0;
  const totalPages = Math.ceil(total / 25);

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-wrap gap-3 bg-white rounded-lg border border-gray-200 p-4">
        <select
          value={entityTypeFilter}
          onChange={(e) => { setEntityTypeFilter(e.target.value); setPage(1); }}
          className="px-3 py-2.5 border border-gray-300 rounded-lg text-sm min-h-[48px] bg-white"
        >
          <option value="">All Entity Types</option>
          <option value="work_order">Work Order</option>
          <option value="user">User</option>
          <option value="site">Site</option>
          <option value="asset">Asset</option>
          <option value="part">Part</option>
          <option value="pm_template">PM Template</option>
          <option value="organization">Organization</option>
        </select>
        <select
          value={actionFilter}
          onChange={(e) => { setActionFilter(e.target.value); setPage(1); }}
          className="px-3 py-2.5 border border-gray-300 rounded-lg text-sm min-h-[48px] bg-white"
        >
          <option value="">All Actions</option>
          <option value="CREATE">Create</option>
          <option value="UPDATE">Update</option>
          <option value="DELETE">Delete</option>
          <option value="STATUS_CHANGE">Status Change</option>
          <option value="LOGIN">Login</option>
        </select>
        <input
          type="date"
          value={dateFrom}
          onChange={(e) => { setDateFrom(e.target.value); setPage(1); }}
          placeholder="From"
          className="px-3 py-2.5 border border-gray-300 rounded-lg text-sm min-h-[48px]"
        />
        <input
          type="date"
          value={dateTo}
          onChange={(e) => { setDateTo(e.target.value); setPage(1); }}
          placeholder="To"
          className="px-3 py-2.5 border border-gray-300 rounded-lg text-sm min-h-[48px]"
        />
      </div>

      {/* Entries */}
      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 size={32} className="animate-spin text-navy-600" />
        </div>
      )}

      {!isLoading && entries.length === 0 && (
        <div className="text-center py-12">
          <FileText size={48} className="mx-auto text-gray-300 mb-3" />
          <p className="text-gray-500">No audit log entries found</p>
        </div>
      )}

      <div className="bg-white rounded-lg border border-gray-200 divide-y divide-gray-100">
        {entries.map((entry: AuditLog) => {
          const isExpanded = expandedId === entry.id;
          return (
            <div key={entry.id}>
              <button
                onClick={() => setExpandedId(isExpanded ? null : entry.id)}
                className="w-full text-left px-4 py-3 hover:bg-gray-50 min-h-[48px] transition-colors"
              >
                <div className="flex items-center gap-3">
                  <div className={`p-1.5 rounded ${
                    entry.action === 'CREATE' ? 'bg-green-100' :
                    entry.action === 'DELETE' ? 'bg-red-100' :
                    'bg-blue-100'
                  }`}>
                    <FileText size={14} className={
                      entry.action === 'CREATE' ? 'text-green-600' :
                      entry.action === 'DELETE' ? 'text-red-600' :
                      'text-blue-600'
                    } />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-medium text-gray-900">{entry.action}</span>
                      <span className="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded-full">
                        {entry.entity_type}
                      </span>
                    </div>
                    <div className="text-xs text-gray-500 mt-0.5">
                      {format(parseISO(entry.created_at), 'MMM d, yyyy h:mm a')}
                    </div>
                  </div>
                  {isExpanded ? (
                    <ChevronDown size={16} className="text-gray-400 shrink-0" />
                  ) : (
                    <ChevronRight size={16} className="text-gray-400 shrink-0" />
                  )}
                </div>
              </button>

              {isExpanded && (
                <div className="px-4 pb-4 bg-gray-50">
                  <div className="space-y-3 text-sm">
                    {entry.old_value && (
                      <div>
                        <div className="text-xs font-medium text-gray-500 mb-1">Old Values</div>
                        <pre className="bg-white border border-gray-200 rounded-lg p-3 text-xs overflow-x-auto max-h-40">
                          {JSON.stringify(entry.old_value, null, 2)}
                        </pre>
                      </div>
                    )}
                    {entry.new_value && (
                      <div>
                        <div className="text-xs font-medium text-gray-500 mb-1">New Values</div>
                        <pre className="bg-white border border-gray-200 rounded-lg p-3 text-xs overflow-x-auto max-h-40">
                          {JSON.stringify(entry.new_value, null, 2)}
                        </pre>
                      </div>
                    )}
                    {!entry.old_value && !entry.new_value && (
                      <p className="text-gray-400 text-xs italic">No detail data available</p>
                    )}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <div className="text-sm text-gray-500">
            Page {page} of {totalPages} ({total} entries)
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setPage(Math.max(1, page - 1))}
              disabled={page <= 1}
              className="px-4 py-2.5 border border-gray-300 rounded-lg text-sm font-medium min-h-[48px] disabled:opacity-50 hover:bg-gray-50"
            >
              Previous
            </button>
            <button
              onClick={() => setPage(Math.min(totalPages, page + 1))}
              disabled={page >= totalPages}
              className="px-4 py-2.5 border border-gray-300 rounded-lg text-sm font-medium min-h-[48px] disabled:opacity-50 hover:bg-gray-50"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
