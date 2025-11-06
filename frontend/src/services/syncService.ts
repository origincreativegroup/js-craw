/**
 * SyncService - Real-time data synchronization service
 * 
 * Provides:
 * - Cache management for job data
 * - Optimistic updates
 * - Conflict resolution
 * - Real-time sync between views
 */

import type { Job } from '../types';

interface CacheEntry<T> {
  data: T;
  timestamp: number;
  version: number;
}

class SyncService {
  private cache: Map<string, CacheEntry<any>> = new Map();
  private listeners: Map<string, Set<(data: any) => void>> = new Map();
  private updateQueue: Map<string, Promise<any>> = new Map();
  private readonly CACHE_TTL = 5 * 60 * 1000; // 5 minutes

  /**
   * Get cached data or fetch if not available/stale
   */
  async get<T>(
    key: string,
    fetcher: () => Promise<T>,
    options?: { forceRefresh?: boolean; ttl?: number }
  ): Promise<T> {
    const entry = this.cache.get(key);
    const now = Date.now();
    const ttl = options?.ttl || this.CACHE_TTL;

    // Return cached data if fresh and not forcing refresh
    if (!options?.forceRefresh && entry && (now - entry.timestamp) < ttl) {
      return entry.data as T;
    }

    // Fetch new data
    try {
      const data = await fetcher();
      this.set(key, data);
      return data;
    } catch (error) {
      // If fetch fails and we have cached data, return it
      if (entry) {
        console.warn(`Failed to fetch ${key}, using cached data`, error);
        return entry.data as T;
      }
      throw error;
    }
  }

  /**
   * Set cached data
   */
  set<T>(key: string, data: T): void {
    const entry = this.cache.get(key);
    const version = entry ? entry.version + 1 : 1;

    this.cache.set(key, {
      data,
      timestamp: Date.now(),
      version,
    });

    // Notify listeners
    this.notify(key, data);
  }

  /**
   * Update data optimistically
   */
  async update<T>(
    key: string,
    updater: (current: T) => T,
    apiCall: () => Promise<T>,
    options?: { rollbackOnError?: boolean }
  ): Promise<T> {
    const entry = this.cache.get(key);
    const current = entry?.data as T;

    // Optimistic update
    const optimistic = updater(current);
    this.set(key, optimistic);

    // Track update in queue to prevent duplicate calls
    if (this.updateQueue.has(key)) {
      return this.updateQueue.get(key)!;
    }

    const updatePromise = (async () => {
      try {
        const result = await apiCall();
        this.set(key, result);
        return result;
      } catch (error) {
        // Rollback on error if requested
        if (options?.rollbackOnError && current) {
          this.set(key, current);
        }
        throw error;
      } finally {
        this.updateQueue.delete(key);
      }
    })();

    this.updateQueue.set(key, updatePromise);
    return updatePromise;
  }

  /**
   * Invalidate cache for a key or pattern
   */
  invalidate(pattern?: string): void {
    if (!pattern) {
      this.cache.clear();
      return;
    }

    // Support wildcard patterns
    const regex = new RegExp(pattern.replace(/\*/g, '.*'));
    for (const key of this.cache.keys()) {
      if (regex.test(key)) {
        this.cache.delete(key);
      }
    }
  }

  /**
   * Subscribe to changes for a key
   */
  subscribe<T>(key: string, callback: (data: T) => void): () => void {
    if (!this.listeners.has(key)) {
      this.listeners.set(key, new Set());
    }
    this.listeners.get(key)!.add(callback);

    // Immediately call with current data if available
    const entry = this.cache.get(key);
    if (entry) {
      callback(entry.data as T);
    }

    // Return unsubscribe function
    return () => {
      const listeners = this.listeners.get(key);
      if (listeners) {
        listeners.delete(callback);
        if (listeners.size === 0) {
          this.listeners.delete(key);
        }
      }
    };
  }

  /**
   * Notify all listeners for a key
   */
  private notify(key: string, data: any): void {
    const listeners = this.listeners.get(key);
    if (listeners) {
      listeners.forEach(callback => {
        try {
          callback(data);
        } catch (error) {
          console.error('Error in sync listener', error);
        }
      });
    }
  }

  /**
   * Get cache statistics
   */
  getStats() {
    return {
      cacheSize: this.cache.size,
      listenerCount: Array.from(this.listeners.values()).reduce(
        (sum, set) => sum + set.size,
        0
      ),
      pendingUpdates: this.updateQueue.size,
    };
  }

  /**
   * Get cached data without fetching
   */
  getCached<T>(key: string): T | null {
    const entry = this.cache.get(key);
    if (entry) {
      return entry.data as T;
    }
    return null;
  }

  /**
   * Clear all cache and listeners
   */
  clear(): void {
    this.cache.clear();
    this.listeners.clear();
    this.updateQueue.clear();
  }
}

// Singleton instance
export const syncService = new SyncService();

// Helper functions for common job operations
export const jobSync = {
  /**
   * Get job with caching
   */
  getJob: async (jobId: number, fetcher: () => Promise<Job>): Promise<Job> => {
    return syncService.get(`job:${jobId}`, fetcher);
  },

  /**
   * Get pipeline jobs with caching
   */
  getPipeline: async (
    fetcher: () => Promise<Record<string, Job[]>>,
    options?: { forceRefresh?: boolean }
  ): Promise<Record<string, Job[]>> => {
    return syncService.get('pipeline:all', fetcher, options);
  },

  /**
   * Update job optimistically
   */
  updateJob: async (
    jobId: number,
    updates: Partial<Job>,
    apiCall: () => Promise<Job>
  ): Promise<Job> => {
    return syncService.update(
      `job:${jobId}`,
      (current: Job) => ({ ...current, ...updates }),
      apiCall,
      { rollbackOnError: true }
    );
  },

  /**
   * Update pipeline stage optimistically
   */
  updateStage: async (
    jobId: number,
    newStage: string,
    apiCall: () => Promise<void>
  ): Promise<void> => {
    // Get current job from cache if available
    const cacheKey = `job:${jobId}`;
    const currentJob = syncService.getCached<Job>(cacheKey);

    // Update individual job optimistically
    if (currentJob) {
      await syncService.update(
        cacheKey,
        (current: Job) => ({ ...current, pipeline_stage: newStage }),
        async () => {
          await apiCall();
          // Return updated job
          return { ...currentJob, pipeline_stage: newStage };
        },
        { rollbackOnError: true }
      );
    } else {
      // If not cached, just call the API
      await apiCall();
    }

    // Invalidate pipeline cache
    syncService.invalidate('pipeline:*');
  },

  /**
   * Subscribe to job changes
   */
  subscribeToJob: (jobId: number, callback: (job: Job) => void): (() => void) => {
    return syncService.subscribe(`job:${jobId}`, callback);
  },

  /**
   * Subscribe to pipeline changes
   */
  subscribeToPipeline: (
    callback: (pipeline: Record<string, Job[]>) => void
  ): (() => void) => {
    return syncService.subscribe('pipeline:all', callback);
  },

  /**
   * Invalidate job cache
   */
  invalidateJob: (jobId: number): void => {
    syncService.invalidate(`job:${jobId}`);
    syncService.invalidate('pipeline:*');
  },
};

export default syncService;

