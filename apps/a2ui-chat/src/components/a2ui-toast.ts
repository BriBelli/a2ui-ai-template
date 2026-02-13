import { LitElement, html, css, nothing } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { toast, type ToastItem } from '../services/toast-service';

/**
 * Toast notification container.
 * Mount once in the app shell: <a2ui-toast></a2ui-toast>
 * Toasts are triggered via the toast service singleton.
 */
@customElement('a2ui-toast')
export class A2UIToast extends LitElement {
  static styles = css`
    :host {
      position: fixed;
      bottom: var(--a2ui-space-6);
      right: var(--a2ui-space-6);
      z-index: var(--a2ui-z-toast, 400);
      display: flex;
      flex-direction: column-reverse;
      gap: var(--a2ui-space-2);
      pointer-events: none;
      max-width: 380px;
    }

    .toast {
      display: flex;
      align-items: flex-start;
      gap: var(--a2ui-space-3);
      padding: var(--a2ui-space-3) var(--a2ui-space-4);
      border-radius: var(--a2ui-radius-lg);
      background: var(--a2ui-bg-elevated);
      border: 1px solid var(--a2ui-border-default);
      box-shadow: var(--a2ui-shadow-lg);
      color: var(--a2ui-text-primary);
      font-family: var(--a2ui-font-family);
      font-size: var(--a2ui-text-sm);
      line-height: var(--a2ui-leading-normal);
      pointer-events: auto;
      animation: slideIn 0.2s cubic-bezier(0.22, 1, 0.36, 1);
      will-change: transform, opacity;
    }

    .toast.removing {
      animation: slideOut 0.15s ease forwards;
    }

    @keyframes slideIn {
      from {
        opacity: 0;
        transform: translateX(16px) scale(0.96);
      }
      to {
        opacity: 1;
        transform: translateX(0) scale(1);
      }
    }

    @keyframes slideOut {
      to {
        opacity: 0;
        transform: translateX(16px) scale(0.96);
      }
    }

    .toast-icon {
      flex-shrink: 0;
      width: 18px;
      height: 18px;
      margin-top: 1px;
    }

    .toast-icon.info { color: var(--a2ui-info); }
    .toast-icon.success { color: var(--a2ui-success); }
    .toast-icon.warning { color: var(--a2ui-warning); }
    .toast-icon.error { color: var(--a2ui-error); }

    .toast-message {
      flex: 1;
      min-width: 0;
      word-break: break-word;
    }

    .toast-close {
      flex-shrink: 0;
      width: 18px;
      height: 18px;
      padding: 0;
      border: none;
      background: none;
      color: var(--a2ui-text-tertiary);
      cursor: pointer;
      border-radius: var(--a2ui-radius-sm);
      display: flex;
      align-items: center;
      justify-content: center;
      transition: color 0.1s ease, background 0.1s ease;
      margin-top: 1px;
    }

    .toast-close:hover {
      color: var(--a2ui-text-primary);
      background: var(--a2ui-bg-hover);
    }
  `;

  @state() private toasts: ToastItem[] = [];
  private removing = new Set<string>();

  private listener = (items: ToastItem[]) => {
    this.toasts = items;
  };

  connectedCallback() {
    super.connectedCallback();
    toast.subscribe(this.listener);
    this.toasts = toast.getAll();
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    toast.unsubscribe(this.listener);
  }

  private handleDismiss(id: string) {
    this.removing.add(id);
    this.requestUpdate();
    // Wait for exit animation, then actually remove
    setTimeout(() => {
      this.removing.delete(id);
      toast.dismiss(id);
    }, 150);
  }

  private iconFor(variant: string) {
    switch (variant) {
      case 'success':
        return html`<svg class="toast-icon success" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>`;
      case 'warning':
        return html`<svg class="toast-icon warning" viewBox="0 0 24 24" fill="currentColor"><path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/></svg>`;
      case 'error':
        return html`<svg class="toast-icon error" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>`;
      default: // info
        return html`<svg class="toast-icon info" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/></svg>`;
    }
  }

  render() {
    if (!this.toasts.length) return nothing;

    return html`
      ${this.toasts.map(
        (t) => html`
        <div class="toast ${this.removing.has(t.id) ? 'removing' : ''}">
          ${this.iconFor(t.variant)}
          <span class="toast-message">${t.message}</span>
          <button class="toast-close" @click=${() =>
            this.handleDismiss(t.id)} aria-label="Dismiss">
            <svg viewBox="0 0 24 24" fill="currentColor" width="18" height="18">
              <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
            </svg>
          </button>
        </div>
      `
      )}
    `;
  }
}
