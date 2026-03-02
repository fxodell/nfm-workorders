/**
 * Service Worker for the Oilfield CMMS PWA.
 *
 * Provides:
 * - Workbox-based caching strategies (NetworkFirst for API, CacheFirst for assets)
 * - Background sync for the offline mutation queue
 * - Push notification handling (FCM)
 * - Automatic cache cleanup on activation
 */

/// <reference lib="webworker" />
declare const self: ServiceWorkerGlobalScope;

import { clientsClaim } from 'workbox-core';
import { cleanupOutdatedCaches, precacheAndRoute } from 'workbox-precaching';
import {
  CacheFirst,
  NetworkFirst,
  StaleWhileRevalidate,
} from 'workbox-strategies';
import { ExpirationPlugin } from 'workbox-expiration';
import { CacheableResponsePlugin } from 'workbox-cacheable-response';
import { registerRoute, NavigationRoute, Route } from 'workbox-routing';
import { BackgroundSyncPlugin } from 'workbox-background-sync';

// ---------------------------------------------------------------------------
// Install & Activate
// ---------------------------------------------------------------------------

// Skip waiting so the new SW activates immediately.
self.skipWaiting();

// Claim all open clients as soon as this SW activates.
clientsClaim();

// Precache the Vite build manifest entries injected at build time.
// Workbox injects the list via `self.__WB_MANIFEST`.
precacheAndRoute(self.__WB_MANIFEST);

// Remove caches left over from previous SW versions.
cleanupOutdatedCaches();

// ---------------------------------------------------------------------------
// Cache Names
// ---------------------------------------------------------------------------

const API_CACHE = 'cmms-api-v1';
const STATIC_CACHE = 'cmms-static-v1';
const IMAGE_CACHE = 'cmms-images-v1';
const FONT_CACHE = 'cmms-fonts-v1';

// ---------------------------------------------------------------------------
// Background Sync for Offline Queue
// ---------------------------------------------------------------------------

const bgSyncPlugin = new BackgroundSyncPlugin('cmms-offline-mutations', {
  maxRetentionTime: 48 * 60, // 48 hours in minutes
  onSync: async ({ queue }) => {
    let entry;
    while ((entry = await queue.shiftRequest())) {
      try {
        await fetch(entry.request.clone());
      } catch (error) {
        // Put it back at the front of the queue and re-throw so
        // the browser knows the sync failed and will retry later.
        await queue.unshiftRequest(entry);
        throw error;
      }
    }
  },
});

// ---------------------------------------------------------------------------
// Route: API Calls (/api/*) - NetworkFirst with 24h cache fallback
// ---------------------------------------------------------------------------

const apiRoute = new Route(
  ({ url }) => url.pathname.startsWith('/api/'),
  new NetworkFirst({
    cacheName: API_CACHE,
    networkTimeoutSeconds: 10,
    plugins: [
      new CacheableResponsePlugin({
        statuses: [0, 200],
      }),
      new ExpirationPlugin({
        maxAgeSeconds: 24 * 60 * 60, // 24 hours
        maxEntries: 500,
        purgeOnQuotaError: true,
      }),
    ],
  }),
  'GET',
);
registerRoute(apiRoute);

// API mutations (POST/PUT/PATCH/DELETE) go through background sync when offline.
const apiMutationRoute = new Route(
  ({ url, request }) =>
    url.pathname.startsWith('/api/') &&
    ['POST', 'PUT', 'PATCH', 'DELETE'].includes(request.method),
  new NetworkFirst({
    cacheName: API_CACHE,
    plugins: [bgSyncPlugin],
  }),
  // We register for each method individually below.
);

// Register mutation methods for background sync.
for (const method of ['POST', 'PUT', 'PATCH', 'DELETE'] as const) {
  registerRoute(
    ({ url }) => url.pathname.startsWith('/api/'),
    new NetworkFirst({
      cacheName: API_CACHE,
      plugins: [bgSyncPlugin],
    }),
    method,
  );
}

// ---------------------------------------------------------------------------
// Route: Static Assets (JS, CSS, WASM) - CacheFirst with 30-day expiry
// ---------------------------------------------------------------------------

registerRoute(
  ({ request, url }) =>
    request.destination === 'script' ||
    request.destination === 'style' ||
    url.pathname.match(/\.(js|css|wasm)$/) !== null,
  new CacheFirst({
    cacheName: STATIC_CACHE,
    plugins: [
      new CacheableResponsePlugin({
        statuses: [0, 200],
      }),
      new ExpirationPlugin({
        maxAgeSeconds: 30 * 24 * 60 * 60, // 30 days
        maxEntries: 200,
        purgeOnQuotaError: true,
      }),
    ],
  }),
);

// ---------------------------------------------------------------------------
// Route: Images & Photos - CacheFirst with 7-day expiry
// ---------------------------------------------------------------------------

registerRoute(
  ({ request, url }) =>
    request.destination === 'image' ||
    url.pathname.match(/\.(png|jpg|jpeg|gif|svg|webp|avif|ico)$/) !== null,
  new CacheFirst({
    cacheName: IMAGE_CACHE,
    plugins: [
      new CacheableResponsePlugin({
        statuses: [0, 200],
      }),
      new ExpirationPlugin({
        maxAgeSeconds: 7 * 24 * 60 * 60, // 7 days
        maxEntries: 300,
        purgeOnQuotaError: true,
      }),
    ],
  }),
);

// ---------------------------------------------------------------------------
// Route: Fonts - CacheFirst with 365-day expiry
// ---------------------------------------------------------------------------

registerRoute(
  ({ request, url }) =>
    request.destination === 'font' ||
    url.pathname.match(/\.(woff2?|ttf|otf|eot)$/) !== null,
  new CacheFirst({
    cacheName: FONT_CACHE,
    plugins: [
      new CacheableResponsePlugin({
        statuses: [0, 200],
      }),
      new ExpirationPlugin({
        maxAgeSeconds: 365 * 24 * 60 * 60, // 1 year
        maxEntries: 30,
        purgeOnQuotaError: true,
      }),
    ],
  }),
);

// ---------------------------------------------------------------------------
// SPA Navigation Fallback
// ---------------------------------------------------------------------------

// For any navigation request that doesn't match a precached URL, serve
// the cached index.html so the SPA router can handle it.
const navigationHandler = new NetworkFirst({
  cacheName: 'cmms-navigations',
  plugins: [
    new CacheableResponsePlugin({ statuses: [200] }),
  ],
});

registerRoute(
  new NavigationRoute(navigationHandler, {
    // Don't intercept API routes or asset routes as navigations.
    denylist: [/^\/api\//, /\.\w+$/],
  }),
);

// ---------------------------------------------------------------------------
// Push Notifications (FCM)
// ---------------------------------------------------------------------------

self.addEventListener('push', (event: PushEvent) => {
  if (!event.data) return;

  let payload: {
    title?: string;
    body?: string;
    icon?: string;
    badge?: string;
    tag?: string;
    data?: Record<string, unknown>;
  };

  try {
    payload = event.data.json();
  } catch {
    payload = { title: 'CMMS Notification', body: event.data.text() };
  }

  const title = payload.title ?? 'Work Order Update';
  const options: NotificationOptions = {
    body: payload.body ?? '',
    icon: payload.icon ?? '/icons/icon-192x192.png',
    badge: payload.badge ?? '/icons/badge-72x72.png',
    tag: payload.tag ?? `cmms-${Date.now()}`,
    data: payload.data ?? {},
    vibrate: [200, 100, 200],
    requireInteraction: true,
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', (event: NotificationEvent) => {
  event.notification.close();

  const notificationData = event.notification.data as Record<string, unknown> | undefined;
  const targetUrl =
    (notificationData?.url as string) ?? '/';

  event.waitUntil(
    self.clients
      .matchAll({ type: 'window', includeUncontrolled: true })
      .then((clientList) => {
        // Focus an existing tab if one is open with the same origin.
        for (const client of clientList) {
          if (client.url.startsWith(self.location.origin) && 'focus' in client) {
            client.focus();
            client.postMessage({
              type: 'NOTIFICATION_CLICK',
              url: targetUrl,
            });
            return;
          }
        }
        // Otherwise open a new window.
        return self.clients.openWindow(targetUrl);
      }),
  );
});

// ---------------------------------------------------------------------------
// Message Handling
// ---------------------------------------------------------------------------

self.addEventListener('message', (event) => {
  if (event.data?.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }

  if (event.data?.type === 'GET_CACHE_STATS') {
    getCacheStats().then((stats) => {
      event.ports?.[0]?.postMessage({ type: 'CACHE_STATS', stats });
    });
  }
});

async function getCacheStats(): Promise<Record<string, number>> {
  const cacheNames = await caches.keys();
  const stats: Record<string, number> = {};
  for (const name of cacheNames) {
    const cache = await caches.open(name);
    const keys = await cache.keys();
    stats[name] = keys.length;
  }
  return stats;
}

// ---------------------------------------------------------------------------
// Activate: Clean old caches
// ---------------------------------------------------------------------------

self.addEventListener('activate', (event) => {
  const currentCaches = new Set([
    API_CACHE,
    STATIC_CACHE,
    IMAGE_CACHE,
    FONT_CACHE,
    'cmms-navigations',
  ]);

  event.waitUntil(
    caches.keys().then((cacheNames) =>
      Promise.all(
        cacheNames
          .filter((name) => name.startsWith('cmms-') && !currentCaches.has(name))
          .map((name) => caches.delete(name)),
      ),
    ),
  );
});
