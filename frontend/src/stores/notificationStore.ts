import { create } from 'zustand';
import type { WSEvent } from '@/types/api';

interface NotificationItem {
  id: string;
  event: WSEvent;
  read: boolean;
  timestamp: string;
}

interface NotificationState {
  items: NotificationItem[];
  unreadCount: number;
  drawerOpen: boolean;

  addNotification: (event: WSEvent) => void;
  markAllRead: () => void;
  markRead: (id: string) => void;
  setDrawerOpen: (open: boolean) => void;
  clearAll: () => void;
}

export const useNotificationStore = create<NotificationState>()((set) => ({
  items: [],
  unreadCount: 0,
  drawerOpen: false,

  addNotification: (event) =>
    set((state) => {
      const item: NotificationItem = {
        id: crypto.randomUUID(),
        event,
        read: false,
        timestamp: new Date().toISOString(),
      };
      const items = [item, ...state.items].slice(0, 50);
      return { items, unreadCount: state.unreadCount + 1 };
    }),

  markAllRead: () =>
    set((state) => ({
      items: state.items.map((i) => ({ ...i, read: true })),
      unreadCount: 0,
    })),

  markRead: (id) =>
    set((state) => ({
      items: state.items.map((i) => (i.id === id ? { ...i, read: true } : i)),
      unreadCount: Math.max(0, state.unreadCount - (state.items.find((i) => i.id === id && !i.read) ? 1 : 0)),
    })),

  setDrawerOpen: (open) => set({ drawerOpen: open }),
  clearAll: () => set({ items: [], unreadCount: 0 }),
}));
