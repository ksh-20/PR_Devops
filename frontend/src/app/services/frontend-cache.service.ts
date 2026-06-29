import { Injectable } from '@angular/core';

interface CacheEntry {
  data: any;
  expiry: number;
}

@Injectable({
  providedIn: 'root'
})
export class FrontendCacheService {
  private cache = new Map<string, CacheEntry>();
  private defaultTtl = 5 * 60 * 1000; // 5 minutes in milliseconds

  get(key: string): any | null {
    const entry = this.cache.get(key);
    if (!entry) {
      return null;
    }
    if (Date.now() > entry.expiry) {
      this.cache.delete(key);
      return null;
    }
    return entry.data;
  }

  set(key: string, data: any, ttlMs: number = this.defaultTtl): void {
    const expiry = Date.now() + ttlMs;
    this.cache.set(key, { data, expiry });
  }

  clear(): void {
    this.cache.clear();
  }

  has(key: string): boolean {
    return this.get(key) !== null;
  }
}
