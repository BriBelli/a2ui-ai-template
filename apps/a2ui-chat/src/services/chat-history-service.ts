/**
 * Chat History Service
 *
 * Persists chat threads to localStorage, scoped per user.
 * Designed as a thin, swappable layer — replace localStorage
 * with IndexedDB or a remote DB later without touching consumers.
 */

import type { ChatMessage } from './chat-service';

// ── Types ────────────────────────────────────────────────

export interface ChatThread {
  id: string;
  title: string;
  messages: ChatMessage[];
  createdAt: number;
  updatedAt: number;
  model?: string;
  provider?: string;
}

// ── Service ──────────────────────────────────────────────

const KEY_PREFIX = 'a2ui_threads';

export class ChatHistoryService {
  private userId: string | null = null;

  /** Call once after auth resolves so threads are user-scoped. */
  setUser(userId: string | null) {
    this.userId = userId;
  }

  // ── CRUD ─────────────────────────────────────────────

  getThreads(): ChatThread[] {
    const raw = localStorage.getItem(this.key());
    if (!raw) return [];
    try {
      const threads: ChatThread[] = JSON.parse(raw);
      return threads.sort((a, b) => b.updatedAt - a.updatedAt);
    } catch {
      return [];
    }
  }

  getThread(id: string): ChatThread | null {
    return this.getThreads().find(t => t.id === id) ?? null;
  }

  saveThread(thread: ChatThread): void {
    const threads = this.getThreads();
    const idx = threads.findIndex(t => t.id === thread.id);
    if (idx >= 0) {
      threads[idx] = thread;
    } else {
      threads.unshift(thread);
    }
    this.write(threads);
  }

  deleteThread(id: string): void {
    this.write(this.getThreads().filter(t => t.id !== id));
  }

  clearAll(): void {
    localStorage.removeItem(this.key());
  }

  // ── Helpers ──────────────────────────────────────────

  /** Build a title from the first user message. */
  static titleFrom(message: string, maxLen = 50): string {
    const trimmed = message.trim().replace(/\n+/g, ' ');
    return trimmed.length > maxLen ? trimmed.slice(0, maxLen) + '…' : trimmed;
  }

  // ── Private ──────────────────────────────────────────

  private key(): string {
    return this.userId ? `${KEY_PREFIX}_${this.userId}` : KEY_PREFIX;
  }

  private write(threads: ChatThread[]): void {
    localStorage.setItem(this.key(), JSON.stringify(threads));
  }
}

export const chatHistoryService = new ChatHistoryService();
