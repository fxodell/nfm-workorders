import { useState, useCallback, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { Loader2, Eye, EyeOff, AlertCircle, HardHat } from 'lucide-react';
import { authApi } from '@/api/auth';
import { useAuthStore } from '@/stores/authStore';
import type { User } from '@/types/api';
import apiClient from '@/api/client';

type LoginStep = 'credentials' | 'mfa';

export default function LoginPage() {
  const navigate = useNavigate();
  const { isAuthenticated, setTokens, setUser, setMfaRequired, mfaSessionToken } = useAuthStore();

  const [step, setStep] = useState<LoginStep>('credentials');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const [mfaCode, setMfaCode] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});

  const mfaInputRef = useRef<HTMLInputElement>(null);

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated) {
      navigate('/dashboard', { replace: true });
    }
  }, [isAuthenticated, navigate]);

  // Focus MFA input when entering MFA step
  useEffect(() => {
    if (step === 'mfa' && mfaInputRef.current) {
      mfaInputRef.current.focus();
    }
  }, [step]);

  const validateCredentials = useCallback((): boolean => {
    const newErrors: Record<string, string> = {};

    if (!email.trim()) {
      newErrors.email = 'Email is required';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      newErrors.email = 'Enter a valid email address';
    }

    if (!password) {
      newErrors.password = 'Password is required';
    } else if (password.length < 8) {
      newErrors.password = 'Password must be at least 8 characters';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }, [email, password]);

  const loginMutation = useMutation({
    mutationFn: () => authApi.login(email, password),
    onSuccess: async (response) => {
      const data = response.data;

      if (data.mfa_required && data.mfa_session_token) {
        setMfaRequired(true, data.mfa_session_token);
        setStep('mfa');
        setMfaCode('');
        return;
      }

      // No MFA required -- complete login
      setTokens(data.access_token, data.refresh_token);

      try {
        const meResponse = await apiClient.get<User>('/users/me');
        setUser(meResponse.data);
      } catch {
        // User profile fetch failed but tokens are set
      }

      navigate('/dashboard', { replace: true });
    },
    onError: (error: unknown) => {
      const axiosError = error as { response?: { status: number; data?: { detail?: string } } };
      if (axiosError.response?.status === 401) {
        setErrors({ form: 'Invalid email or password. Please try again.' });
      } else if (axiosError.response?.status === 423) {
        setErrors({ form: 'Account is locked. Contact your administrator.' });
      } else if (axiosError.response?.status === 429) {
        setErrors({ form: 'Too many attempts. Please wait and try again.' });
      } else {
        setErrors({ form: axiosError.response?.data?.detail || 'An unexpected error occurred. Please try again.' });
      }
    },
  });

  const mfaConfirmMutation = useMutation({
    mutationFn: () => {
      if (!mfaSessionToken) throw new Error('MFA session token missing');
      return authApi.mfaConfirm(mfaSessionToken, mfaCode);
    },
    onSuccess: async (response) => {
      const data = response.data;
      setTokens(data.access_token, data.refresh_token);

      try {
        const meResponse = await apiClient.get<User>('/users/me');
        setUser(meResponse.data);
      } catch {
        // User profile fetch failed but tokens are set
      }

      navigate('/dashboard', { replace: true });
    },
    onError: (error: unknown) => {
      const axiosError = error as { response?: { status: number; data?: { detail?: string } } };
      if (axiosError.response?.status === 401) {
        setErrors({ mfa: 'Invalid verification code. Please try again.' });
      } else if (axiosError.response?.status === 410) {
        setErrors({ mfa: 'Verification session expired. Please log in again.' });
        setStep('credentials');
        setMfaRequired(false);
      } else {
        setErrors({ mfa: axiosError.response?.data?.detail || 'Verification failed. Please try again.' });
      }
      setMfaCode('');
    },
  });

  const handleCredentialsSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateCredentials()) return;
    setErrors({});
    loginMutation.mutate();
  };

  const handleMfaSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (mfaCode.length !== 6) {
      setErrors({ mfa: 'Enter the 6-digit code from your authenticator app' });
      return;
    }
    setErrors({});
    mfaConfirmMutation.mutate();
  };

  const handleMfaCodeChange = (value: string) => {
    const cleaned = value.replace(/\D/g, '').slice(0, 6);
    setMfaCode(cleaned);
    if (errors.mfa) {
      setErrors({});
    }
  };

  const handleBackToLogin = () => {
    setStep('credentials');
    setMfaRequired(false);
    setMfaCode('');
    setErrors({});
  };

  const isSubmitting = loginMutation.isPending || mfaConfirmMutation.isPending;

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gradient-to-br from-navy-900 via-navy-800 to-gray-900 px-4">
      {/* Company branding */}
      <div className="mb-8 text-center">
        <div className="inline-flex items-center justify-center w-20 h-20 bg-white/10 backdrop-blur rounded-2xl mb-4">
          <HardHat size={40} className="text-amber-400" />
        </div>
        <h1 className="text-3xl font-bold text-white tracking-tight">Oilfield CMMS</h1>
        <p className="text-navy-300 mt-1 text-sm">Computerized Maintenance Management System</p>
      </div>

      {/* Login card */}
      <div className="w-full max-w-sm bg-white rounded-2xl shadow-2xl p-8">
        {step === 'credentials' && (
          <form onSubmit={handleCredentialsSubmit} noValidate>
            <h2 className="text-xl font-bold text-gray-900 mb-1">Sign in</h2>
            <p className="text-sm text-gray-500 mb-6">Enter your credentials to continue</p>

            {errors.form && (
              <div className="flex items-start gap-2 p-3 mb-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                <AlertCircle size={16} className="shrink-0 mt-0.5" />
                <span>{errors.form}</span>
              </div>
            )}

            {/* Email */}
            <div className="mb-4">
              <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
                Email address
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value);
                  if (errors.email) setErrors((prev) => ({ ...prev, email: '' }));
                }}
                className={`w-full h-12 px-4 border rounded-lg text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-navy-500 focus:border-transparent transition-colors ${
                  errors.email ? 'border-red-300 bg-red-50' : 'border-gray-300'
                }`}
                placeholder="you@company.com"
                disabled={isSubmitting}
              />
              {errors.email && (
                <p className="mt-1 text-xs text-red-600">{errors.email}</p>
              )}
            </div>

            {/* Password */}
            <div className="mb-4">
              <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
                Password
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    if (errors.password) setErrors((prev) => ({ ...prev, password: '' }));
                  }}
                  className={`w-full h-12 px-4 pr-12 border rounded-lg text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-navy-500 focus:border-transparent transition-colors ${
                    errors.password ? 'border-red-300 bg-red-50' : 'border-gray-300'
                  }`}
                  placeholder="Enter your password"
                  disabled={isSubmitting}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-2 text-gray-400 hover:text-gray-600 min-w-[44px] min-h-[44px] flex items-center justify-center"
                  tabIndex={-1}
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
              {errors.password && (
                <p className="mt-1 text-xs text-red-600">{errors.password}</p>
              )}
            </div>

            {/* Remember me */}
            <div className="flex items-center mb-6">
              <label className="flex items-center gap-2 cursor-pointer min-h-[48px]">
                <input
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(e) => setRememberMe(e.target.checked)}
                  className="w-4 h-4 rounded border-gray-300 text-navy-600 focus:ring-navy-500"
                />
                <span className="text-sm text-gray-600">Remember me</span>
              </label>
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full h-12 bg-navy-900 hover:bg-navy-800 disabled:bg-navy-400 text-white font-semibold rounded-lg transition-colors flex items-center justify-center gap-2"
            >
              {isSubmitting ? (
                <>
                  <Loader2 size={18} className="animate-spin" />
                  Signing in...
                </>
              ) : (
                'Sign in'
              )}
            </button>
          </form>
        )}

        {step === 'mfa' && (
          <form onSubmit={handleMfaSubmit} noValidate>
            <h2 className="text-xl font-bold text-gray-900 mb-1">Verification required</h2>
            <p className="text-sm text-gray-500 mb-6">
              Enter the 6-digit code from your authenticator app
            </p>

            {errors.mfa && (
              <div className="flex items-start gap-2 p-3 mb-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                <AlertCircle size={16} className="shrink-0 mt-0.5" />
                <span>{errors.mfa}</span>
              </div>
            )}

            {/* MFA Code Input */}
            <div className="mb-6">
              <label htmlFor="mfa-code" className="block text-sm font-medium text-gray-700 mb-1">
                Verification code
              </label>
              <input
                ref={mfaInputRef}
                id="mfa-code"
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={6}
                value={mfaCode}
                onChange={(e) => handleMfaCodeChange(e.target.value)}
                className={`w-full h-14 px-4 border rounded-lg text-gray-900 text-center text-2xl font-mono tracking-[0.5em] placeholder-gray-300 focus:outline-none focus:ring-2 focus:ring-navy-500 focus:border-transparent transition-colors ${
                  errors.mfa ? 'border-red-300 bg-red-50' : 'border-gray-300'
                }`}
                placeholder="000000"
                disabled={isSubmitting}
              />
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={isSubmitting || mfaCode.length !== 6}
              className="w-full h-12 bg-navy-900 hover:bg-navy-800 disabled:bg-navy-400 text-white font-semibold rounded-lg transition-colors flex items-center justify-center gap-2 mb-3"
            >
              {isSubmitting ? (
                <>
                  <Loader2 size={18} className="animate-spin" />
                  Verifying...
                </>
              ) : (
                'Verify'
              )}
            </button>

            {/* Back to login */}
            <button
              type="button"
              onClick={handleBackToLogin}
              className="w-full h-12 text-gray-600 hover:text-gray-900 hover:bg-gray-50 font-medium rounded-lg transition-colors"
            >
              Back to sign in
            </button>
          </form>
        )}
      </div>

      {/* Footer */}
      <p className="mt-8 text-navy-400 text-xs">
        &copy; {new Date().getFullYear()} Oilfield CMMS. All rights reserved.
      </p>
    </div>
  );
}
