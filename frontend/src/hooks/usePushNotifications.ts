import { useState, useCallback } from 'react';
import { notificationsApi } from '@/api/notifications';

export function usePushNotifications() {
  const [permissionState, setPermissionState] = useState<NotificationPermission>(
    typeof Notification !== 'undefined' ? Notification.permission : 'default'
  );
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isIOS = /iPhone|iPad|iPod/.test(navigator.userAgent);
  const isStandalone = 'standalone' in window.navigator && (window.navigator as { standalone?: boolean }).standalone === true;
  const needsInstall = isIOS && !isStandalone;

  const requestPermission = useCallback(async () => {
    if (needsInstall) {
      setError('Push notifications require the app to be installed to your Home Screen.');
      return false;
    }

    setIsLoading(true);
    setError(null);

    try {
      const permission = await Notification.requestPermission();
      setPermissionState(permission);

      if (permission === 'granted') {
        // Dynamic import Firebase to avoid loading it unless needed
        const { initializeApp } = await import('firebase/app');
        const { getMessaging, getToken } = await import('firebase/messaging');

        const app = initializeApp({
          // These would come from env vars in production
          apiKey: import.meta.env.VITE_FIREBASE_API_KEY || '',
          authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || '',
          projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || '',
          messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || '',
          appId: import.meta.env.VITE_FIREBASE_APP_ID || '',
        });

        const messaging = getMessaging(app);
        const token = await getToken(messaging, {
          vapidKey: import.meta.env.VITE_FIREBASE_VAPID_KEY || '',
        });

        if (token) {
          await notificationsApi.storeFcmToken(token);
          localStorage.setItem('ofmaint-push-permission', 'granted');
          setIsLoading(false);
          return true;
        }
      }

      setIsLoading(false);
      return false;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to set up push notifications');
      setIsLoading(false);
      return false;
    }
  }, [needsInstall]);

  return {
    permissionState,
    isLoading,
    error,
    isIOS,
    isStandalone,
    needsInstall,
    requestPermission,
  };
}
