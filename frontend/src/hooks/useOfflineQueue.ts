import { useEffect, useCallback, useRef } from 'react';
import { openDB, DBSchema, IDBPDatabase } from 'idb';
import { useOfflineQueueStore } from '@/stores/offlineQueueStore';
import apiClient from '@/api/client';
import type { OfflineQueueEntry } from '@/types/api';

interface OfflineDB extends DBSchema {
  offline_queue: {
    key: string;
    value: OfflineQueueEntry;
    indexes: { 'by-created': string };
  };
}

const DB_NAME = 'ofmaint-offline';
const DB_VERSION = 1;

async function getDB(): Promise<IDBPDatabase<OfflineDB>> {
  return openDB<OfflineDB>(DB_NAME, DB_VERSION, {
    upgrade(db) {
      const store = db.createObjectStore('offline_queue', { keyPath: 'id' });
      store.createIndex('by-created', 'created_at');
    },
  });
}

export function useOfflineQueue() {
  const {
    setPendingCount, setIsSyncing, setLastSyncAt,
    setOldestUnsyncedAt, checkWarnings,
  } = useOfflineQueueStore();
  const syncingRef = useRef(false);
  const warningIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refreshCount = useCallback(async () => {
    const db = await getDB();
    const all = await db.getAll('offline_queue');
    const pending = all.filter((e) => e.status !== 'FAILED' || e.retry_count < 3);
    setPendingCount(pending.length);

    if (pending.length > 0) {
      const oldest = pending.reduce((a, b) =>
        a.created_at < b.created_at ? a : b
      );
      setOldestUnsyncedAt(oldest.created_at);
    } else {
      setOldestUnsyncedAt(null);
    }
    checkWarnings();
  }, [setPendingCount, setOldestUnsyncedAt, checkWarnings]);

  const enqueue = useCallback(
    async (entry: Omit<OfflineQueueEntry, 'retry_count' | 'status'>) => {
      const db = await getDB();
      const fullEntry: OfflineQueueEntry = {
        ...entry,
        retry_count: 0,
        status: 'PENDING',
      };
      await db.put('offline_queue', fullEntry);
      await refreshCount();
    },
    [refreshCount]
  );

  const syncQueue = useCallback(async (): Promise<{
    synced: number;
    failed: number;
    conflicts: OfflineQueueEntry[];
  }> => {
    if (syncingRef.current) return { synced: 0, failed: 0, conflicts: [] };
    syncingRef.current = true;
    setIsSyncing(true);

    const db = await getDB();
    const all = await db.getAllFromIndex('offline_queue', 'by-created');
    let synced = 0;
    let failed = 0;
    const conflicts: OfflineQueueEntry[] = [];

    for (const entry of all) {
      if (entry.status === 'FAILED' && entry.retry_count >= 3) continue;

      try {
        entry.status = 'SYNCING';
        await db.put('offline_queue', entry);

        const response = await apiClient.request({
          method: entry.method as 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE',
          url: entry.endpoint,
          data: entry.payload,
          headers: entry.id ? { 'Idempotency-Key': entry.id } : {},
        });

        if (response.status >= 200 && response.status < 300) {
          await db.delete('offline_queue', entry.id);
          synced++;
        }
      } catch (error: unknown) {
        const axiosError = error as { response?: { status: number } };
        if (axiosError.response?.status === 409) {
          // Conflict - server state diverged
          entry.status = 'FAILED';
          await db.put('offline_queue', entry);
          conflicts.push(entry);
        } else {
          // Retry with backoff
          entry.retry_count++;
          entry.status = entry.retry_count >= 3 ? 'FAILED' : 'PENDING';
          await db.put('offline_queue', entry);
          failed++;

          if (entry.retry_count < 3) {
            const backoff = Math.pow(4, entry.retry_count) * 1000;
            await new Promise((r) => setTimeout(r, backoff));
          }
        }
      }
    }

    setIsSyncing(false);
    setLastSyncAt(new Date().toISOString());
    syncingRef.current = false;
    await refreshCount();
    return { synced, failed, conflicts };
  }, [refreshCount, setIsSyncing, setLastSyncAt]);

  const removeEntry = useCallback(
    async (id: string) => {
      const db = await getDB();
      await db.delete('offline_queue', id);
      await refreshCount();
    },
    [refreshCount]
  );

  const getEntry = useCallback(async (id: string) => {
    const db = await getDB();
    return db.get('offline_queue', id);
  }, []);

  const getAllEntries = useCallback(async () => {
    const db = await getDB();
    return db.getAll('offline_queue');
  }, []);

  // Auto-sync on reconnect
  useEffect(() => {
    const handleOnline = () => {
      // Probe health endpoint before syncing
      fetch('/api/v1/health')
        .then((r) => {
          if (r.ok) syncQueue();
        })
        .catch(() => {});
    };

    window.addEventListener('online', handleOnline);
    refreshCount();

    // Check warnings periodically
    warningIntervalRef.current = setInterval(() => {
      checkWarnings();
    }, 60000); // Every minute

    return () => {
      window.removeEventListener('online', handleOnline);
      if (warningIntervalRef.current) clearInterval(warningIntervalRef.current);
    };
  }, [syncQueue, refreshCount, checkWarnings]);

  return { enqueue, syncQueue, removeEntry, getEntry, getAllEntries, refreshCount };
}
