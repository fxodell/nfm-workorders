import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';
import { useAuthStore } from '@/stores/authStore';

const API_URL = import.meta.env.VITE_API_URL || '';

const apiClient = axios.create({
  baseURL: `${API_URL}/api/v1`,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,
});

let refreshPromise: Promise<string> | null = null;

function isTokenExpired(token: string): boolean {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return payload.exp * 1000 < Date.now();
  } catch {
    return true;
  }
}

function processQueue(error: unknown, token: string | null = null) {
  // No-op: queue-based approach replaced by shared promise
}

apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const { accessToken, refreshToken, setTokens, logout } = useAuthStore.getState();

  // Proactively refresh if the access token is expired
  if (accessToken && isTokenExpired(accessToken) && refreshToken && !refreshPromise) {
    refreshPromise = axios
      .post(`${API_URL}/api/v1/auth/refresh`, { refresh_token: refreshToken })
      .then((response) => {
        const { access_token, refresh_token } = response.data;
        setTokens(access_token, refresh_token);
        return access_token as string;
      })
      .catch((err) => {
        console.error('Token refresh failed:', err);
        logout();
        window.location.href = '/login';
        throw err;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }

  if (accessToken && config.headers) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      const { refreshToken, setTokens, logout } = useAuthStore.getState();

      if (!refreshToken) {
        logout();
        window.location.href = '/login';
        return Promise.reject(error);
      }

      // Use a shared promise so concurrent 401s all await the same refresh
      if (!refreshPromise) {
        refreshPromise = axios
          .post(`${API_URL}/api/v1/auth/refresh`, { refresh_token: refreshToken })
          .then((response) => {
            const { access_token, refresh_token } = response.data;
            setTokens(access_token, refresh_token);
            return access_token as string;
          })
          .catch((err) => {
            console.error('Token refresh failed:', err);
            logout();
            window.location.href = '/login';
            throw err;
          })
          .finally(() => {
            refreshPromise = null;
          });
      }

      try {
        const newToken = await refreshPromise;
        if (originalRequest.headers) {
          originalRequest.headers.Authorization = `Bearer ${newToken}`;
        }
        return apiClient(originalRequest);
      } catch (refreshError) {
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

export default apiClient;
