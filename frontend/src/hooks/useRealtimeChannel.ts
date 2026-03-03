import { useEffect, useRef, useCallback } from 'react';
import { useAuthStore } from '@/stores/authStore';
import { useNotificationStore } from '@/stores/notificationStore';
import { authApi } from '@/api/auth';
import type { WSEvent } from '@/types/api';

const WS_URL = import.meta.env.VITE_WS_URL || `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}`;
const HEARTBEAT_INTERVAL = 30000;
const PONG_TIMEOUT = 10000;
const MAX_BACKOFF = 30000;

export function useRealtimeChannel(onEvent?: (event: WSEvent) => void) {
  const wsRef = useRef<WebSocket | null>(null);
  const heartbeatRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pongTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttempts = useRef(0);
  const reconnectTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const { isAuthenticated } = useAuthStore();
  const { addNotification } = useNotificationStore();

  const cleanup = useCallback(() => {
    if (heartbeatRef.current) clearInterval(heartbeatRef.current);
    if (pongTimeoutRef.current) clearTimeout(pongTimeoutRef.current);
    if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current);
    if (wsRef.current) {
      wsRef.current.onclose = null;
      wsRef.current.onerror = null;
      wsRef.current.onmessage = null;
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  const connect = useCallback(async () => {
    if (!isAuthenticated) return;

    try {
      const response = await authApi.getWsToken();
      const wsToken = response.data.token;

      cleanup();

      const ws = new WebSocket(`${WS_URL}/ws?token=${wsToken}`);
      wsRef.current = ws;

      ws.onopen = () => {
        reconnectAttempts.current = 0;

        // Start heartbeat
        heartbeatRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'pong' }));
          }
        }, HEARTBEAT_INTERVAL);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          // Handle heartbeat ping
          if (data.type === 'ping') {
            if (pongTimeoutRef.current) clearTimeout(pongTimeoutRef.current);
            ws.send(JSON.stringify({ type: 'pong' }));
            return;
          }

          // Process event
          const wsEvent = data as WSEvent;
          addNotification(wsEvent);
          onEvent?.(wsEvent);
        } catch (e) {
          console.warn('WebSocket message parse error:', e);
        }
      };

      ws.onclose = (event) => {
        cleanup();
        if (event.code !== 1000 && isAuthenticated) {
          // Reconnect with exponential backoff
          const delay = Math.min(
            1000 * Math.pow(2, reconnectAttempts.current),
            MAX_BACKOFF
          );
          reconnectAttempts.current++;
          reconnectTimeout.current = setTimeout(connect, delay);
        }
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch {
      // Token fetch failed, retry
      const delay = Math.min(
        1000 * Math.pow(2, reconnectAttempts.current),
        MAX_BACKOFF
      );
      reconnectAttempts.current++;
      reconnectTimeout.current = setTimeout(connect, delay);
    }
  }, [isAuthenticated, cleanup, addNotification, onEvent]);

  useEffect(() => {
    connect();
    return cleanup;
  }, [connect, cleanup]);

  return {
    isConnected: wsRef.current?.readyState === WebSocket.OPEN,
    reconnect: connect,
  };
}
