/**
 * Lightweight toast notification service.
 *
 * Usage:
 *   import { toast } from './toast-service';
 *   toast.error('Something went wrong');
 *   toast.success('Saved!');
 *   toast.info('Searching the web…');
 *   toast.warning('Rate limit reached');
 */

export type ToastVariant = 'info' | 'success' | 'warning' | 'error';

export interface ToastItem {
  id: string;
  variant: ToastVariant;
  message: string;
}

type Listener = (toasts: ToastItem[]) => void;

class ToastService {
  private items: ToastItem[] = [];
  private listeners = new Set<Listener>();
  private timers = new Map<string, number>();

  /** Auto-dismiss duration in ms. */
  private duration = 5000;

  // ── Public API ─────────────────────────────────────────

  info(message: string) {
    this.add('info', message);
  }
  success(message: string) {
    this.add('success', message);
  }
  warning(message: string) {
    this.add('warning', message);
  }
  error(message: string) {
    this.add('error', message);
  }

  dismiss(id: string) {
    this.items = this.items.filter((t) => t.id !== id);
    clearTimeout(this.timers.get(id));
    this.timers.delete(id);
    this.notify();
  }

  // ── Subscribe / unsubscribe (used by the component) ────

  subscribe(fn: Listener) {
    this.listeners.add(fn);
  }
  unsubscribe(fn: Listener) {
    this.listeners.delete(fn);
  }
  getAll(): ToastItem[] {
    return this.items;
  }

  // ── Internal ───────────────────────────────────────────

  private add(variant: ToastVariant, message: string) {
    const id = crypto.randomUUID();
    this.items = [...this.items, { id, variant, message }];
    this.notify();

    // Auto-dismiss
    const timer = window.setTimeout(() => this.dismiss(id), this.duration);
    this.timers.set(id, timer);
  }

  private notify() {
    this.listeners.forEach((fn) => fn(this.items));
  }
}

/** Singleton instance — import this everywhere. */
export const toast = new ToastService();
