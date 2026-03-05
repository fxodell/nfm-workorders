import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  User, Mail, Phone, Shield, Lock, Bell, BellOff, LogOut, Save,
  Eye, EyeOff, Loader2, AlertTriangle, Award, Calendar,
  Smartphone, CheckCircle2, XCircle, Clock, ToggleLeft, ToggleRight,
  ChevronDown, ChevronRight,
} from 'lucide-react';
import { format, parseISO, differenceInDays, isPast } from 'date-fns';
import { authApi } from '@/api/auth';
import { notificationsApi } from '@/api/notifications';
import { shiftsApi } from '@/api/shifts';
import apiClient from '@/api/client';
import { useAuthStore } from '@/stores/authStore';
import { usePushNotifications } from '@/hooks/usePushNotifications';
import type { NotificationPref, Certification, ShiftSchedule } from '@/types/api';
import { UserRole } from '@/types/enums';

const roleColors: Record<UserRole, string> = {
  [UserRole.SUPER_ADMIN]: 'bg-purple-100 text-purple-800',
  [UserRole.ADMIN]: 'bg-red-100 text-red-800',
  [UserRole.SUPERVISOR]: 'bg-blue-100 text-blue-800',
  [UserRole.OPERATOR]: 'bg-green-100 text-green-800',
  [UserRole.TECHNICIAN]: 'bg-yellow-100 text-yellow-800',
  [UserRole.READ_ONLY]: 'bg-gray-100 text-gray-600',
  [UserRole.COST_ANALYST]: 'bg-indigo-100 text-indigo-800',
};

const dayLabels = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

export default function ProfilePage() {
  const queryClient = useQueryClient();
  const { user, setUser, logout } = useAuthStore();

  const [editingProfile, setEditingProfile] = useState(false);
  const [profileName, setProfileName] = useState(user?.name || '');
  const [profilePhone, setProfilePhone] = useState(user?.phone || '');

  const [showChangePassword, setShowChangePassword] = useState(false);
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showCurrentPw, setShowCurrentPw] = useState(false);
  const [showNewPw, setShowNewPw] = useState(false);

  const [showMfaSetup, setShowMfaSetup] = useState(false);
  const [mfaCode, setMfaCode] = useState('');
  const [showMfaDisable, setShowMfaDisable] = useState(false);
  const [mfaDisableCode, setMfaDisableCode] = useState('');

  const [certsExpanded, setCertsExpanded] = useState(false);
  const [shiftsExpanded, setShiftsExpanded] = useState(false);

  // Push notifications
  const {
    permissionState,
    isLoading: pushLoading,
    error: pushError,
    needsInstall,
    requestPermission,
  } = usePushNotifications();

  const pushEnabled = permissionState === 'granted' && localStorage.getItem('ofmaint-push-permission') === 'granted';

  // Notification preferences
  const { data: notifPrefs = [] } = useQuery({
    queryKey: ['notification-prefs'],
    queryFn: async () => {
      const res = await notificationsApi.getPrefs();
      return res.data;
    },
  });

  // Certifications
  const { data: certifications = [] } = useQuery({
    queryKey: ['certifications'],
    queryFn: async () => {
      const res = await apiClient.get<Certification[]>('/users/me/certifications');
      return res.data;
    },
  });

  // Shift assignments
  const { data: shifts = [] } = useQuery({
    queryKey: ['my-shifts'],
    queryFn: async () => {
      const res = await apiClient.get<ShiftSchedule[]>('/users/me/shifts');
      return res.data;
    },
  });

  // MFA setup
  const { data: mfaSetupData, mutate: initMfaSetup, isPending: mfaSetupLoading } = useMutation({
    mutationFn: () => authApi.mfaSetup(),
  });

  // Mutations
  const updateProfileMutation = useMutation({
    mutationFn: async () => {
      const res = await apiClient.patch('/users/me', {
        name: profileName,
        phone: profilePhone || undefined,
      });
      return res.data;
    },
    onSuccess: (data) => {
      setUser(data as typeof user & Record<string, unknown> as NonNullable<typeof user>);
      setEditingProfile(false);
    },
  });

  const changePasswordMutation = useMutation({
    mutationFn: async () => {
      await apiClient.post('/users/me/change-password', {
        current_password: currentPassword,
        new_password: newPassword,
      });
    },
    onSuccess: () => {
      setShowChangePassword(false);
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    },
  });

  const mfaVerifyMutation = useMutation({
    mutationFn: () => authApi.mfaVerify(mfaCode),
    onSuccess: () => {
      if (user) {
        setUser({ ...user, mfa_enabled: true });
      }
      setShowMfaSetup(false);
      setMfaCode('');
    },
  });

  const mfaDisableMutation = useMutation({
    mutationFn: () => authApi.mfaDisable(mfaDisableCode),
    onSuccess: () => {
      if (user) {
        setUser({ ...user, mfa_enabled: false });
      }
      setShowMfaDisable(false);
      setMfaDisableCode('');
    },
  });

  const updateNotifPrefMutation = useMutation({
    mutationFn: (data: NotificationPref) => notificationsApi.updatePrefs(data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notification-prefs'] }),
  });

  const handleClearFcm = async () => {
    try {
      await notificationsApi.clearFcmToken();
      localStorage.removeItem('ofmaint-push-permission');
    } catch {
      // Silently handle
    }
  };

  const passwordsMatch = newPassword === confirmPassword;
  const passwordValid = newPassword.length >= 8;

  // Sort certifications: expiring soon first
  const sortedCerts = useMemo(() => {
    return [...certifications].sort((a, b) => {
      if (!a.expires_at) return 1;
      if (!b.expires_at) return -1;
      return new Date(a.expires_at).getTime() - new Date(b.expires_at).getTime();
    });
  }, [certifications]);

  const expiringCerts = useMemo(() => {
    return certifications.filter((c) => {
      if (!c.expires_at) return false;
      const daysUntil = differenceInDays(parseISO(c.expires_at), new Date());
      return daysUntil <= 30 && daysUntil >= 0;
    });
  }, [certifications]);

  const expiredCerts = useMemo(() => {
    return certifications.filter((c) => c.expires_at && isPast(parseISO(c.expires_at)));
  }, [certifications]);

  if (!user) return null;

  return (
    <div className="space-y-4 max-w-2xl mx-auto">
      {/* Profile Header */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="flex items-center gap-4 mb-4">
          <div className="w-16 h-16 bg-navy-100 rounded-full flex items-center justify-center text-navy-800 font-bold text-2xl shrink-0">
            {user.name?.charAt(0).toUpperCase() || 'U'}
          </div>
          <div className="flex-1 min-w-0">
            <h1 className="text-xl font-bold text-gray-900">{user.name}</h1>
            <div className="flex items-center gap-2 mt-1 flex-wrap">
              <span className={`px-2.5 py-0.5 text-xs rounded-full font-semibold ${roleColors[user.role] || 'bg-gray-100'}`}>
                {user.role}
              </span>
              {user.mfa_enabled && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-green-100 text-green-700 text-xs rounded-full font-medium">
                  <Shield size={10} />
                  MFA
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="space-y-2 text-sm text-gray-600">
          <div className="flex items-center gap-2">
            <Mail size={14} className="text-gray-400 shrink-0" />
            {user.email}
          </div>
          {user.phone && (
            <div className="flex items-center gap-2">
              <Phone size={14} className="text-gray-400 shrink-0" />
              {user.phone}
            </div>
          )}
        </div>
      </div>

      {/* Certification warnings */}
      {(expiringCerts.length > 0 || expiredCerts.length > 0) && (
        <div className={`rounded-lg border p-4 ${
          expiredCerts.length > 0 ? 'bg-red-50 border-red-200' : 'bg-yellow-50 border-yellow-200'
        }`}>
          <div className="flex items-start gap-2">
            <AlertTriangle size={18} className={expiredCerts.length > 0 ? 'text-red-600 shrink-0 mt-0.5' : 'text-yellow-600 shrink-0 mt-0.5'} />
            <div>
              {expiredCerts.length > 0 && (
                <p className="text-sm font-medium text-red-800">
                  {expiredCerts.length} certification{expiredCerts.length !== 1 ? 's' : ''} expired
                </p>
              )}
              {expiringCerts.length > 0 && (
                <p className="text-sm font-medium text-yellow-800">
                  {expiringCerts.length} certification{expiringCerts.length !== 1 ? 's' : ''} expiring within 30 days
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Edit Profile */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">Edit Profile</h2>
          {!editingProfile && (
            <button
              onClick={() => setEditingProfile(true)}
              className="text-sm font-medium text-navy-600 min-h-[48px] px-3"
            >
              Edit
            </button>
          )}
        </div>

        {editingProfile ? (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
              <input
                type="text"
                value={profileName}
                onChange={(e) => setProfileName(e.target.value)}
                className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm min-h-[48px] focus:ring-2 focus:ring-navy-500 focus:border-navy-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Phone</label>
              <input
                type="tel"
                value={profilePhone}
                onChange={(e) => setProfilePhone(e.target.value)}
                placeholder="+1 (555) 123-4567"
                className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm min-h-[48px] focus:ring-2 focus:ring-navy-500 focus:border-navy-500"
              />
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => {
                  setEditingProfile(false);
                  setProfileName(user.name);
                  setProfilePhone(user.phone || '');
                }}
                className="flex-1 px-4 py-2.5 border border-gray-300 rounded-lg font-medium text-gray-700 min-h-[48px]"
              >
                Cancel
              </button>
              <button
                onClick={() => updateProfileMutation.mutate()}
                disabled={!profileName.trim() || updateProfileMutation.isPending}
                className="flex-1 px-4 py-2.5 bg-navy-900 text-white rounded-lg font-medium min-h-[48px] disabled:opacity-50 flex items-center justify-center gap-2"
              >
                <Save size={16} />
                {updateProfileMutation.isPending ? 'Saving...' : 'Save'}
              </button>
            </div>
            {updateProfileMutation.isError && (
              <p className="text-red-600 text-sm">Failed to update profile. Please try again.</p>
            )}
          </div>
        ) : (
          <div className="space-y-2 text-sm text-gray-600">
            <div className="flex items-center gap-2">
              <User size={14} className="text-gray-400" />
              <span className="font-medium text-gray-900">{user.name}</span>
            </div>
            <div className="flex items-center gap-2">
              <Phone size={14} className="text-gray-400" />
              <span>{user.phone || 'Not set'}</span>
            </div>
          </div>
        )}
      </div>

      {/* Change Password */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <button
          onClick={() => setShowChangePassword(!showChangePassword)}
          className="flex items-center justify-between w-full min-h-[48px]"
        >
          <div className="flex items-center gap-2">
            <Lock size={18} className="text-gray-600" />
            <h2 className="text-lg font-semibold text-gray-900">Change Password</h2>
          </div>
          {showChangePassword ? (
            <ChevronDown size={18} className="text-gray-400" />
          ) : (
            <ChevronRight size={18} className="text-gray-400" />
          )}
        </button>

        {showChangePassword && (
          <div className="mt-4 space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Current Password</label>
              <div className="relative">
                <input
                  type={showCurrentPw ? 'text' : 'password'}
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  className="w-full px-3 py-2.5 pr-12 border border-gray-300 rounded-lg text-sm min-h-[48px] focus:ring-2 focus:ring-navy-500 focus:border-navy-500"
                />
                <button
                  type="button"
                  onClick={() => setShowCurrentPw(!showCurrentPw)}
                  className="absolute right-1 top-1/2 -translate-y-1/2 p-2 min-h-[48px] min-w-[48px] flex items-center justify-center"
                >
                  {showCurrentPw ? <EyeOff size={16} className="text-gray-400" /> : <Eye size={16} className="text-gray-400" />}
                </button>
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">New Password</label>
              <div className="relative">
                <input
                  type={showNewPw ? 'text' : 'password'}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="Minimum 8 characters"
                  className="w-full px-3 py-2.5 pr-12 border border-gray-300 rounded-lg text-sm min-h-[48px] focus:ring-2 focus:ring-navy-500 focus:border-navy-500"
                />
                <button
                  type="button"
                  onClick={() => setShowNewPw(!showNewPw)}
                  className="absolute right-1 top-1/2 -translate-y-1/2 p-2 min-h-[48px] min-w-[48px] flex items-center justify-center"
                >
                  {showNewPw ? <EyeOff size={16} className="text-gray-400" /> : <Eye size={16} className="text-gray-400" />}
                </button>
              </div>
              {newPassword && !passwordValid && (
                <p className="text-red-500 text-xs mt-1">Password must be at least 8 characters</p>
              )}
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Confirm New Password</label>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm min-h-[48px] focus:ring-2 focus:ring-navy-500 focus:border-navy-500"
              />
              {confirmPassword && !passwordsMatch && (
                <p className="text-red-500 text-xs mt-1">Passwords do not match</p>
              )}
            </div>
            <button
              onClick={() => changePasswordMutation.mutate()}
              disabled={
                !currentPassword || !newPassword || !confirmPassword ||
                !passwordsMatch || !passwordValid || changePasswordMutation.isPending
              }
              className="w-full px-4 py-2.5 bg-navy-900 text-white rounded-lg font-medium min-h-[48px] disabled:opacity-50"
            >
              {changePasswordMutation.isPending ? 'Changing...' : 'Change Password'}
            </button>
            {changePasswordMutation.isError && (
              <p className="text-red-600 text-sm">Failed to change password. Check your current password and try again.</p>
            )}
            {changePasswordMutation.isSuccess && (
              <p className="text-green-600 text-sm">Password changed successfully.</p>
            )}
          </div>
        )}
      </div>

      {/* MFA Section */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Shield size={18} className="text-gray-600" />
            <h2 className="text-lg font-semibold text-gray-900">Multi-Factor Authentication</h2>
          </div>
          {user.mfa_enabled ? (
            <span className="inline-flex items-center gap-1 px-2.5 py-1 bg-green-100 text-green-700 text-xs rounded-full font-semibold">
              <CheckCircle2 size={12} />
              Enabled
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 px-2.5 py-1 bg-gray-100 text-gray-500 text-xs rounded-full font-semibold">
              Disabled
            </span>
          )}
        </div>

        <div className="mt-4">
          {user.mfa_enabled ? (
            <>
              {!showMfaDisable ? (
                <button
                  onClick={() => setShowMfaDisable(true)}
                  className="px-4 py-2.5 border border-red-300 text-red-600 rounded-lg font-medium min-h-[48px] hover:bg-red-50"
                >
                  Disable MFA
                </button>
              ) : (
                <div className="space-y-3 border border-red-200 rounded-lg p-4 bg-red-50">
                  <p className="text-sm text-red-700 font-medium">Enter your MFA code to confirm disabling:</p>
                  <input
                    type="text"
                    inputMode="numeric"
                    maxLength={6}
                    value={mfaDisableCode}
                    onChange={(e) => setMfaDisableCode(e.target.value.replace(/\D/g, ''))}
                    placeholder="000000"
                    className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm text-center text-lg font-mono tracking-widest min-h-[48px] focus:ring-2 focus:ring-red-500 focus:border-red-500"
                    autoFocus
                  />
                  <div className="flex gap-3">
                    <button
                      onClick={() => { setShowMfaDisable(false); setMfaDisableCode(''); }}
                      className="flex-1 px-4 py-2.5 border border-gray-300 rounded-lg font-medium text-gray-700 min-h-[48px]"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={() => mfaDisableMutation.mutate()}
                      disabled={mfaDisableCode.length !== 6 || mfaDisableMutation.isPending}
                      className="flex-1 px-4 py-2.5 bg-red-600 text-white rounded-lg font-medium min-h-[48px] disabled:opacity-50"
                    >
                      {mfaDisableMutation.isPending ? 'Disabling...' : 'Confirm Disable'}
                    </button>
                  </div>
                  {mfaDisableMutation.isError && (
                    <p className="text-red-600 text-sm text-center">Invalid code. Please try again.</p>
                  )}
                </div>
              )}
            </>
          ) : (
            <>
              {!showMfaSetup ? (
                <button
                  onClick={() => {
                    setShowMfaSetup(true);
                    initMfaSetup();
                  }}
                  className="px-4 py-2.5 bg-navy-900 text-white rounded-lg font-medium min-h-[48px]"
                >
                  Enable MFA
                </button>
              ) : (
                <div className="space-y-4 border border-gray-200 rounded-lg p-4">
                  {mfaSetupLoading && (
                    <div className="flex items-center justify-center py-8">
                      <Loader2 size={24} className="animate-spin text-navy-600" />
                    </div>
                  )}

                  {mfaSetupData?.data && (
                    <>
                      <p className="text-sm text-gray-600">
                        Scan this QR code with your authenticator app, then enter the verification code.
                      </p>
                      <div className="flex justify-center">
                        <img
                          src={mfaSetupData.data.qr_code_data_url}
                          alt="MFA QR Code"
                          className="w-48 h-48"
                        />
                      </div>
                      <div className="text-center">
                        <p className="text-xs text-gray-500 mb-1">Or enter this secret manually:</p>
                        <code className="text-xs bg-gray-100 px-3 py-1 rounded font-mono break-all">
                          {mfaSetupData.data.secret}
                        </code>
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Verification Code</label>
                        <input
                          type="text"
                          inputMode="numeric"
                          maxLength={6}
                          value={mfaCode}
                          onChange={(e) => setMfaCode(e.target.value.replace(/\D/g, ''))}
                          placeholder="000000"
                          className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm text-center text-lg font-mono tracking-widest min-h-[48px] focus:ring-2 focus:ring-navy-500 focus:border-navy-500"
                          autoFocus
                        />
                      </div>
                      <div className="flex gap-3">
                        <button
                          onClick={() => {
                            setShowMfaSetup(false);
                            setMfaCode('');
                          }}
                          className="flex-1 px-4 py-2.5 border border-gray-300 rounded-lg font-medium text-gray-700 min-h-[48px]"
                        >
                          Cancel
                        </button>
                        <button
                          onClick={() => mfaVerifyMutation.mutate()}
                          disabled={mfaCode.length !== 6 || mfaVerifyMutation.isPending}
                          className="flex-1 px-4 py-2.5 bg-navy-900 text-white rounded-lg font-medium min-h-[48px] disabled:opacity-50"
                        >
                          {mfaVerifyMutation.isPending ? 'Verifying...' : 'Verify & Enable'}
                        </button>
                      </div>
                      {mfaVerifyMutation.isError && (
                        <p className="text-red-600 text-sm text-center">Invalid code. Please try again.</p>
                      )}
                    </>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Push Notifications */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="flex items-center gap-2 mb-4">
          <Smartphone size={18} className="text-gray-600" />
          <h2 className="text-lg font-semibold text-gray-900">Push Notifications</h2>
        </div>

        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-gray-700">
              {pushEnabled ? 'Push notifications are enabled' : 'Receive real-time push notifications'}
            </p>
            {needsInstall && (
              <p className="text-xs text-orange-600 mt-1">
                Install this app to your Home Screen to enable push notifications
              </p>
            )}
          </div>
          {pushEnabled ? (
            <button
              onClick={handleClearFcm}
              className="p-3 min-h-[48px] min-w-[48px] flex items-center justify-center"
            >
              <ToggleRight size={28} className="text-green-600" />
            </button>
          ) : (
            <button
              onClick={requestPermission}
              disabled={pushLoading || needsInstall}
              className="p-3 min-h-[48px] min-w-[48px] flex items-center justify-center disabled:opacity-50"
            >
              <ToggleLeft size={28} className="text-gray-400" />
            </button>
          )}
        </div>

        {pushError && (
          <p className="text-red-600 text-sm mt-2">{pushError}</p>
        )}
      </div>

      {/* Notification Preferences */}
      {notifPrefs.length > 0 && (
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <div className="flex items-center gap-2 mb-4">
            <Bell size={18} className="text-gray-600" />
            <h2 className="text-lg font-semibold text-gray-900">Notification Preferences</h2>
          </div>

          <div className="space-y-3">
            {notifPrefs.map((pref) => (
              <div
                key={pref.area_id}
                className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0"
              >
                <div className="text-sm font-medium text-gray-900 min-w-0 flex-1 truncate">
                  Area {pref.area_id?.slice(0, 8) ?? 'Unknown'}
                </div>
                <div className="flex items-center gap-4 shrink-0">
                  <label className="flex items-center gap-2 cursor-pointer min-h-[48px]">
                    <span className="text-xs text-gray-500">Push</span>
                    <button
                      onClick={() =>
                        updateNotifPrefMutation.mutate({
                          ...pref,
                          push_enabled: !pref.push_enabled,
                        })
                      }
                      className="min-h-[48px] min-w-[48px] flex items-center justify-center"
                    >
                      {pref.push_enabled ? (
                        <ToggleRight size={24} className="text-green-600" />
                      ) : (
                        <ToggleLeft size={24} className="text-gray-400" />
                      )}
                    </button>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer min-h-[48px]">
                    <span className="text-xs text-gray-500">Email</span>
                    <button
                      onClick={() =>
                        updateNotifPrefMutation.mutate({
                          ...pref,
                          email_enabled: !pref.email_enabled,
                        })
                      }
                      className="min-h-[48px] min-w-[48px] flex items-center justify-center"
                    >
                      {pref.email_enabled ? (
                        <ToggleRight size={24} className="text-green-600" />
                      ) : (
                        <ToggleLeft size={24} className="text-gray-400" />
                      )}
                    </button>
                  </label>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Certifications */}
      <div className="bg-white rounded-lg border border-gray-200">
        <button
          onClick={() => setCertsExpanded(!certsExpanded)}
          className="w-full flex items-center justify-between p-6 min-h-[48px]"
        >
          <div className="flex items-center gap-2">
            <Award size={18} className="text-gray-600" />
            <h2 className="text-lg font-semibold text-gray-900">Certifications</h2>
            {certifications.length > 0 && (
              <span className="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded-full font-medium">
                {certifications.length}
              </span>
            )}
          </div>
          {certsExpanded ? (
            <ChevronDown size={18} className="text-gray-400" />
          ) : (
            <ChevronRight size={18} className="text-gray-400" />
          )}
        </button>

        {certsExpanded && (
          <div className="px-6 pb-6">
            {sortedCerts.length === 0 ? (
              <p className="text-gray-500 text-sm">No certifications on file</p>
            ) : (
              <div className="space-y-3">
                {sortedCerts.map((cert) => {
                  const isExpired = cert.expires_at && isPast(parseISO(cert.expires_at));
                  const isExpiringSoon = cert.expires_at && !isExpired &&
                    differenceInDays(parseISO(cert.expires_at), new Date()) <= 30;

                  return (
                    <div
                      key={cert.id}
                      className={`rounded-lg border p-3 ${
                        isExpired ? 'border-red-300 bg-red-50' :
                        isExpiringSoon ? 'border-yellow-300 bg-yellow-50' :
                        'border-gray-200'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-gray-900 text-sm">{cert.cert_name}</span>
                            {isExpired && (
                              <span className="px-2 py-0.5 bg-red-100 text-red-700 text-xs rounded-full font-semibold flex items-center gap-1">
                                <XCircle size={10} /> Expired
                              </span>
                            )}
                            {isExpiringSoon && (
                              <span className="px-2 py-0.5 bg-yellow-100 text-yellow-700 text-xs rounded-full font-semibold flex items-center gap-1">
                                <AlertTriangle size={10} /> Expiring Soon
                              </span>
                            )}
                          </div>
                          {cert.cert_number && (
                            <p className="text-xs text-gray-500 mt-0.5">#{cert.cert_number}</p>
                          )}
                          {cert.issued_by && (
                            <p className="text-xs text-gray-500">Issued by: {cert.issued_by}</p>
                          )}
                        </div>
                        <div className="text-right text-xs text-gray-500 shrink-0">
                          {cert.issued_date && (
                            <div>Issued: {format(parseISO(cert.issued_date), 'MMM d, yyyy')}</div>
                          )}
                          {cert.expires_at && (
                            <div className={isExpired ? 'text-red-600 font-medium' : isExpiringSoon ? 'text-yellow-700 font-medium' : ''}>
                              Expires: {format(parseISO(cert.expires_at), 'MMM d, yyyy')}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Shift Assignments */}
      <div className="bg-white rounded-lg border border-gray-200">
        <button
          onClick={() => setShiftsExpanded(!shiftsExpanded)}
          className="w-full flex items-center justify-between p-6 min-h-[48px]"
        >
          <div className="flex items-center gap-2">
            <Clock size={18} className="text-gray-600" />
            <h2 className="text-lg font-semibold text-gray-900">Shift Assignments</h2>
            {shifts.length > 0 && (
              <span className="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded-full font-medium">
                {shifts.length}
              </span>
            )}
          </div>
          {shiftsExpanded ? (
            <ChevronDown size={18} className="text-gray-400" />
          ) : (
            <ChevronRight size={18} className="text-gray-400" />
          )}
        </button>

        {shiftsExpanded && (
          <div className="px-6 pb-6">
            {shifts.length === 0 ? (
              <p className="text-gray-500 text-sm">No shift assignments</p>
            ) : (
              <div className="space-y-3">
                {shifts.map((shift) => (
                  <div key={shift.id} className="rounded-lg border border-gray-200 p-3">
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-medium text-gray-900 text-sm">{shift.name}</span>
                      {!shift.is_active && (
                        <span className="px-2 py-0.5 bg-gray-100 text-gray-500 text-xs rounded-full">
                          Inactive
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-3 text-xs text-gray-500">
                      <span>
                        {shift.start_time} - {shift.end_time}
                      </span>
                      <span className="text-gray-300">|</span>
                      <span>
                        {shift.days_of_week.map((d) => dayLabels[d]).join(', ')}
                      </span>
                    </div>
                    <div className="text-xs text-gray-400 mt-1">
                      {shift.timezone}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Theme / Display (future) */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="flex items-center gap-2">
          <Eye size={18} className="text-gray-600" />
          <h2 className="text-lg font-semibold text-gray-900">Display Preferences</h2>
        </div>
        <p className="text-sm text-gray-500 mt-2">
          Theme and display customization options coming soon.
        </p>
      </div>

      {/* Logout */}
      <button
        onClick={logout}
        className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-red-50 border border-red-200 text-red-700 rounded-lg font-semibold min-h-[48px] active:bg-red-100 transition-colors"
      >
        <LogOut size={18} />
        Sign Out
      </button>
    </div>
  );
}
