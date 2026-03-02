import apiClient from './client';
import type { LoginResponse, TokenResponse, MFASetupResponse, WSTokenResponse } from '@/types/api';

export const authApi = {
  login: (email: string, password: string) =>
    apiClient.post<LoginResponse>('/auth/login', { email, password }),

  refresh: (refreshToken: string) =>
    apiClient.post<TokenResponse>('/auth/refresh', { refresh_token: refreshToken }),

  logout: (refreshToken: string) =>
    apiClient.post('/auth/logout', { refresh_token: refreshToken }),

  getWsToken: () =>
    apiClient.get<WSTokenResponse>('/auth/ws-token'),

  mfaSetup: () =>
    apiClient.post<MFASetupResponse>('/auth/mfa/setup'),

  mfaVerify: (code: string) =>
    apiClient.post('/auth/mfa/verify', { code }),

  mfaConfirm: (mfaSessionToken: string, code: string) =>
    apiClient.post<TokenResponse>('/auth/mfa/confirm', {
      mfa_session_token: mfaSessionToken, code,
    }),

  mfaDisable: (code: string) =>
    apiClient.post('/auth/mfa/disable', { code }),

  requestPasswordReset: (email: string) =>
    apiClient.post('/auth/password-reset-request', { email }),

  resetPassword: (token: string, newPassword: string) =>
    apiClient.post('/auth/password-reset', { token, new_password: newPassword }),
};
