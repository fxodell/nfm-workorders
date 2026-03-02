import apiClient from './client';
import type { NotificationPref } from '@/types/api';

export const notificationsApi = {
  getPrefs: () => apiClient.get<NotificationPref[]>('/users/me/notification-prefs'),
  updatePrefs: (data: NotificationPref) =>
    apiClient.patch('/users/me/notification-prefs', data),
  storeFcmToken: (token: string) =>
    apiClient.post('/users/me/fcm-token', { fcm_token: token }),
  clearFcmToken: () => apiClient.delete('/users/me/fcm-token'),
};
