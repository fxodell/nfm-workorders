import { create } from 'zustand';

interface OfflineQueueState {
  pendingCount: number;
  isSyncing: boolean;
  lastSyncAt: string | null;
  oldestUnsyncedAt: string | null;
  showWarning24h: boolean;
  showWarning48h: boolean;

  setPendingCount: (count: number) => void;
  setIsSyncing: (syncing: boolean) => void;
  setLastSyncAt: (time: string) => void;
  setOldestUnsyncedAt: (time: string | null) => void;
  checkWarnings: () => void;
}

export const useOfflineQueueStore = create<OfflineQueueState>()((set, get) => ({
  pendingCount: 0,
  isSyncing: false,
  lastSyncAt: null,
  oldestUnsyncedAt: null,
  showWarning24h: false,
  showWarning48h: false,

  setPendingCount: (count) => set({ pendingCount: count }),
  setIsSyncing: (syncing) => set({ isSyncing: syncing }),
  setLastSyncAt: (time) => set({ lastSyncAt: time }),
  setOldestUnsyncedAt: (time) => set({ oldestUnsyncedAt: time }),

  checkWarnings: () => {
    const { oldestUnsyncedAt } = get();
    if (!oldestUnsyncedAt) {
      set({ showWarning24h: false, showWarning48h: false });
      return;
    }
    const ageMs = Date.now() - new Date(oldestUnsyncedAt).getTime();
    const hours = ageMs / (1000 * 60 * 60);
    set({
      showWarning24h: hours >= 24 && hours < 48,
      showWarning48h: hours >= 48,
    });
  },
}));
