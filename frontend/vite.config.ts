import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { VitePWA } from 'vite-plugin-pwa';
import path from 'path';

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.ico', 'apple-touch-icon.png', 'mask-icon.svg'],
      manifest: {
        name: 'OilfieldMaint',
        short_name: 'OFMaint',
        description: 'Oilfield maintenance work order tracking',
        display: 'standalone',
        start_url: '/',
        theme_color: '#1e3a5f',
        background_color: '#ffffff',
        icons: [
          { src: '/pwa-192x192.png', sizes: '192x192', type: 'image/png' },
          { src: '/pwa-512x512.png', sizes: '512x512', type: 'image/png' },
          { src: '/pwa-512x512.png', sizes: '512x512', type: 'image/png', purpose: 'any maskable' },
        ],
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],
        runtimeCaching: [
          {
            urlPattern: /^https?:\/\/.*\/api\/v1\/dashboard\/.*/i,
            handler: 'NetworkFirst',
            options: { cacheName: 'dashboard-cache', expiration: { maxEntries: 50, maxAgeSeconds: 300 } },
          },
          {
            urlPattern: /^https?:\/\/.*\/api\/v1\/work-orders.*/i,
            handler: 'NetworkFirst',
            options: { cacheName: 'work-orders-cache', expiration: { maxEntries: 200, maxAgeSeconds: 600 } },
          },
          {
            urlPattern: /^https?:\/\/.*\/api\/v1\/sites.*/i,
            handler: 'NetworkFirst',
            options: { cacheName: 'sites-cache', expiration: { maxEntries: 100, maxAgeSeconds: 3600 } },
          },
          {
            urlPattern: /^https?:\/\/.*\/api\/v1\/assets.*/i,
            handler: 'NetworkFirst',
            options: { cacheName: 'assets-cache', expiration: { maxEntries: 200, maxAgeSeconds: 3600 } },
          },
          {
            urlPattern: /^https?:\/\/.*\/api\/v1\/parts.*/i,
            handler: 'NetworkFirst',
            options: { cacheName: 'parts-cache', expiration: { maxEntries: 100, maxAgeSeconds: 3600 } },
          },
          {
            urlPattern: /\.(?:png|jpg|jpeg|svg|gif|webp)$/i,
            handler: 'CacheFirst',
            options: { cacheName: 'static-images', expiration: { maxEntries: 100, maxAgeSeconds: 2592000 } },
          },
          {
            urlPattern: /\.(?:woff2?|ttf|eot)$/i,
            handler: 'CacheFirst',
            options: { cacheName: 'static-fonts', expiration: { maxEntries: 20, maxAgeSeconds: 31536000 } },
          },
        ],
      },
    }),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    host: '0.0.0.0',
    allowedHosts: ['workorders.nfmconsulting.com'],
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://backend:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://backend:8000',
        ws: true,
      },
    },
  },
});
