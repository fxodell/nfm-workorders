/**
 * Offline write-queue manager backed by IndexedDB.
 *
 * Uses the `idb` library for a Promise-based IndexedDB wrapper.
 * All mutations made while offline are queued here and replayed
 * in order when connectivity is restored.
 */

import { openDB, type DBSchema, type IDBPDatabase } from 'idb';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface QueueEntry {
  /** Auto-incremented primary key. */
  id: number;
  /** HTTP method (POST, PUT, PATCH, DELETE). */
  method: string;
  /** Target URL. */
  url: string;
  /** Serialised request body (JSON string or null). */
  body: string | null;
  /** Request headers as a plain object. */
  headers: Record<string, string>;
  /** Client-generated idempotency key to prevent duplicate processing. */
  idempotencyKey: string;
  /** ISO-8601 timestamp when the entry was created. */
  createdAt: string;
  /** Number of times this entry has been retried. */
  retryCount: number;
  /** Last error message, if any. */
  lastError: string | null;
  /** Whether the server responded with 409 Conflict. */
  conflicted: boolean;
}

export type NewQueueEntry = Omit<
  QueueEntry,
  'id' | 'createdAt' | 'retryCount' | 'lastError' | 'conflicted'
>;

export interface QueueStats {
  pending: number;
  conflicted: number;
  oldestEntryAge: number | null; // milliseconds
  hasStaleEntries: boolean; // > 24 hours
  hasCriticallyStaleEntries: boolean; // > 48 hours
}

// ---------------------------------------------------------------------------
// IndexedDB Schema
// ---------------------------------------------------------------------------

interface OfflineQueueDB extends DBSchema {
  'pending-mutations': {
    key: number;
    value: QueueEntry;
    indexes: {
      'by-created': string;
      'by-conflicted': number; // 0 or 1
    };
  };
}

const DB_NAME = 'cmms-offline-queue';
const STORE_NAME = 'pending-mutations';
const DB_VERSION = 1;

const MAX_RETRIES = 5;
const STALE_THRESHOLD_MS = 24 * 60 * 60 * 1000; // 24 hours
const CRITICAL_STALE_THRESHOLD_MS = 48 * 60 * 60 * 1000; // 48 hours

// ---------------------------------------------------------------------------
// Database Initialisation
// ---------------------------------------------------------------------------

let dbPromise: Promise<IDBPDatabase<OfflineQueueDB>> | null = null;

function getDB(): Promise<IDBPDatabase<OfflineQueueDB>> {
  if (!dbPromise) {
    dbPromise = openDB<OfflineQueueDB>(DB_NAME, DB_VERSION, {
      upgrade(db) {
        const store = db.createObjectStore(STORE_NAME, {
          keyPath: 'id',
          autoIncrement: true,
        });
        store.createIndex('by-created', 'createdAt');
        store.createIndex('by-conflicted', 'conflicted');
      },
      blocked() {
        console.warn('[OfflineSync] Database upgrade blocked by another tab.');
      },
      blocking() {
        console.warn('[OfflineSync] This tab is blocking a DB upgrade in another tab.');
      },
      terminated() {
        console.error('[OfflineSync] Database connection unexpectedly terminated.');
        dbPromise = null;
      },
    });
  }
  return dbPromise;
}

// ---------------------------------------------------------------------------
// Queue Operations
// ---------------------------------------------------------------------------

/**
 * Add a mutation to the offline queue.
 *
 * @returns The auto-generated queue entry ID.
 */
export async function enqueue(
  method: string,
  url: string,
  body: unknown | null,
  headers: Record<string, string> = {},
): Promise<number> {
  const db = await getDB();

  const idempotencyKey =
    headers['X-Idempotency-Key'] ??
    headers['x-idempotency-key'] ??
    crypto.randomUUID();

  const entry: Omit<QueueEntry, 'id'> = {
    method: method.toUpperCase(),
    url,
    body: body != null ? JSON.stringify(body) : null,
    headers: {
      ...headers,
      'X-Idempotency-Key': idempotencyKey,
    },
    idempotencyKey,
    createdAt: new Date().toISOString(),
    retryCount: 0,
    lastError: null,
    conflicted: false,
  };

  const id = await db.add(STORE_NAME, entry as QueueEntry);
  notifyListeners();
  return id as number;
}

/**
 * Process all pending (non-conflicted) queue entries in FIFO order.
 *
 * Failed entries are retried up to `MAX_RETRIES` times with exponential
 * backoff. Entries that receive a 409 Conflict response are marked as
 * conflicted and skipped on subsequent runs.
 */
export async function processQueue(): Promise<void> {
  if (!navigator.onLine) return;

  const db = await getDB();
  const tx = db.transaction(STORE_NAME, 'readonly');
  const allEntries = await tx.store.getAll();
  await tx.done;

  // Process in insertion order (by auto-increment id).
  const pending = allEntries
    .filter((e) => !e.conflicted && e.retryCount < MAX_RETRIES)
    .sort((a, b) => a.id - b.id);

  for (const entry of pending) {
    try {
      const response = await fetch(entry.url, {
        method: entry.method,
        headers: entry.headers,
        body: entry.body,
      });

      if (response.status === 409) {
        // Server conflict -- mark and skip.
        await markConflicted(entry.id, `Server returned 409 Conflict`);
        continue;
      }

      if (!response.ok) {
        // Retriable server error (5xx) or unexpected client error.
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      // Success -- remove from queue.
      await removeEntry(entry.id);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : String(error);

      const updatedRetryCount = entry.retryCount + 1;
      if (updatedRetryCount >= MAX_RETRIES) {
        // Max retries exhausted -- leave in queue but record the error.
        await updateEntry(entry.id, {
          retryCount: updatedRetryCount,
          lastError: `Max retries (${MAX_RETRIES}) exceeded. Last: ${message}`,
        });
      } else {
        await updateEntry(entry.id, {
          retryCount: updatedRetryCount,
          lastError: message,
        });

        // Exponential backoff: 1s, 2s, 4s, 8s, 16s
        const backoffMs = Math.pow(2, updatedRetryCount - 1) * 1000;
        await sleep(backoffMs);
      }
    }
  }

  notifyListeners();
}

/**
 * Return the number of pending (non-conflicted, retryable) entries.
 */
export async function getQueueLength(): Promise<number> {
  const db = await getDB();
  const all = await db.getAll(STORE_NAME);
  return all.filter((e) => !e.conflicted && e.retryCount < MAX_RETRIES).length;
}

/**
 * Return the oldest queue entry, useful for staleness warnings.
 */
export async function getOldestEntry(): Promise<QueueEntry | undefined> {
  const db = await getDB();
  const tx = db.transaction(STORE_NAME, 'readonly');
  const index = tx.store.index('by-created');
  const cursor = await index.openCursor();
  await tx.done;
  return cursor?.value;
}

/**
 * Return all entries currently in the queue (including conflicted).
 */
export async function getAllEntries(): Promise<QueueEntry[]> {
  const db = await getDB();
  return db.getAll(STORE_NAME);
}

/**
 * Remove all entries from the queue.
 */
export async function clearQueue(): Promise<void> {
  const db = await getDB();
  await db.clear(STORE_NAME);
  notifyListeners();
}

/**
 * Remove a specific entry by ID.
 */
export async function removeEntry(id: number): Promise<void> {
  const db = await getDB();
  await db.delete(STORE_NAME, id);
  notifyListeners();
}

// ---------------------------------------------------------------------------
// Queue Stats (for OfflineQueueBanner component)
// ---------------------------------------------------------------------------

/**
 * Compute aggregate queue statistics for UI display.
 */
export async function getQueueStats(): Promise<QueueStats> {
  const db = await getDB();
  const all = await db.getAll(STORE_NAME);

  const now = Date.now();
  let pending = 0;
  let conflicted = 0;
  let oldestAge: number | null = null;

  for (const entry of all) {
    if (entry.conflicted) {
      conflicted++;
    } else if (entry.retryCount < MAX_RETRIES) {
      pending++;
    }

    const age = now - new Date(entry.createdAt).getTime();
    if (oldestAge === null || age > oldestAge) {
      oldestAge = age;
    }
  }

  return {
    pending,
    conflicted,
    oldestEntryAge: oldestAge,
    hasStaleEntries: oldestAge !== null && oldestAge > STALE_THRESHOLD_MS,
    hasCriticallyStaleEntries:
      oldestAge !== null && oldestAge > CRITICAL_STALE_THRESHOLD_MS,
  };
}

// ---------------------------------------------------------------------------
// Internal Helpers
// ---------------------------------------------------------------------------

async function markConflicted(id: number, reason: string): Promise<void> {
  const db = await getDB();
  const entry = await db.get(STORE_NAME, id);
  if (!entry) return;

  await db.put(STORE_NAME, {
    ...entry,
    conflicted: true,
    lastError: reason,
  });

  notifyListeners();
}

async function updateEntry(
  id: number,
  updates: Partial<QueueEntry>,
): Promise<void> {
  const db = await getDB();
  const entry = await db.get(STORE_NAME, id);
  if (!entry) return;

  await db.put(STORE_NAME, { ...entry, ...updates });
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// ---------------------------------------------------------------------------
// Change Listeners (for reactive UI updates)
// ---------------------------------------------------------------------------

type QueueChangeListener = (stats: QueueStats) => void;
const listeners = new Set<QueueChangeListener>();

/**
 * Subscribe to queue changes. Returns an unsubscribe function.
 */
export function onQueueChange(listener: QueueChangeListener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

async function notifyListeners(): Promise<void> {
  if (listeners.size === 0) return;
  const stats = await getQueueStats();
  for (const listener of listeners) {
    try {
      listener(stats);
    } catch {
      // Swallow listener errors to prevent cascading failures.
    }
  }
}

// ---------------------------------------------------------------------------
// Auto-process on Connectivity Restore
// ---------------------------------------------------------------------------

if (typeof window !== 'undefined') {
  window.addEventListener('online', () => {
    processQueue().catch((err) => {
      console.error('[OfflineSync] Failed to process queue on reconnect:', err);
    });
  });
}

// ---------------------------------------------------------------------------
// Exports (default export for convenience)
// ---------------------------------------------------------------------------

const offlineSync = {
  enqueue,
  processQueue,
  getQueueLength,
  getOldestEntry,
  getAllEntries,
  clearQueue,
  removeEntry,
  getQueueStats,
  onQueueChange,
};

export default offlineSync;
