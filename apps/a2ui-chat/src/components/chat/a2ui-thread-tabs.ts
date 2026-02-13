import { LitElement, html, css, nothing } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import type { ChatThread } from '../../services/chat-history-service';

/**
 * Horizontal tab bar for switching between chat threads.
 *
 * Events:
 *  - new-chat          — user clicked the "+" button
 *  - switch-thread     — { threadId: string }
 *  - delete-thread     — { threadId: string }
 *  - rename-thread     — { threadId: string, title: string }
 */
@customElement('a2ui-thread-tabs')
export class A2UIThreadTabs extends LitElement {
  static styles = css`
    :host {
      display: block;
      background: var(--a2ui-bg-primary);
      border-bottom: 1px solid var(--a2ui-border-subtle);
    }

    .tab-bar {
      display: flex;
      align-items: center;
      height: 36px;
      overflow-x: auto;
      overflow-y: hidden;
      scrollbar-width: thin;
      padding: 0 var(--a2ui-space-2);
      gap: 2px;
    }

    /* Hide scrollbar on WebKit while keeping scroll */
    .tab-bar::-webkit-scrollbar {
      height: 0;
    }

    /* ── New-chat button ───────────────────────────────── */

    .new-btn {
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      width: 28px;
      height: 28px;
      background: transparent;
      border: none;
      margin-right: 4px;
      color: var(--a2ui-text-tertiary);
      cursor: pointer;
      transition: background-color 120ms ease, color 120ms ease;
    }

    .new-btn:hover {
      background: var(--a2ui-bg-hover);
      color: var(--a2ui-accent);
    }

    .new-btn svg {
      width: 18px;
      height: 18px;
    }

    /* ── Divider between + and tabs ───────────────────── */

    .bar-divider {
      width: 1px;
      align-self: center;
      height: 16px;
      background: var(--a2ui-border-default);
      flex-shrink: 0;
      margin: 0 2px;
    }

    /* ── Individual tab ────────────────────────────────── */

    .tab {
      display: inline-flex;
      align-items: center;
      gap: 2px;
      flex: 0 0 auto;
      max-width: 220px;
      height: 24px;
      padding: 0 4px 0 8px;
      background: none;
      border: 0;
      border-radius: 6px;
      color: var(--a2ui-text-tertiary);
      font-family: var(--a2ui-font-family);
      font-size: var(--a2ui-text-xs);
      font-weight: var(--a2ui-font-medium);
      cursor: pointer;
      white-space: nowrap;
      transition:
        background-color 120ms ease,
        color 120ms ease,
        border-color 120ms ease;
    }

    .tab:hover {
      color: var(--a2ui-text-primary);
    }

    .tab.active {
      background: var(--a2ui-bg-hover);
      border-color: var(--a2ui-border-default);
      color: var(--a2ui-text-primary);
    }

    /* ── Tab title (truncates) ─────────────────────────── */

    .tab-title {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      pointer-events: none;
      line-height: 1.2;
    }

    /* ── Inline rename input ───────────────────────────── */

    .rename-input {
      width: 120px;
      padding: 1px 4px;
      border: 1px solid var(--a2ui-accent);
      border-radius: var(--a2ui-radius-sm);
      background: var(--a2ui-bg-input);
      color: var(--a2ui-text-primary);
      font-family: var(--a2ui-font-family);
      font-size: 12px;
      outline: none;
    }

    /* ── Close (x) on tab ──────────────────────────────── */

    .tab-close {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      flex: 0 0 auto;
      width: 14px;
      height: 14px;
      border-radius: 3px;
      background: transparent;
      border: none;
      padding: 0;
      color: var(--a2ui-text-tertiary);
      cursor: pointer;
      margin-left: 2px;
      opacity: 0;
      transition:
        opacity 120ms ease,
        background-color 120ms ease,
        color 120ms ease;
    }

    /* Show on tab hover or when tab is active */
    .tab:hover .tab-close,
    .tab.active .tab-close {
      opacity: 0.6;
    }

    .tab-close svg {
      width: 10px;
      height: 10px;
    }

    /* Brighten on direct hover of the x */
    .tab-close:hover {
      opacity: 1;
      background: var(--a2ui-bg-active);
      color: var(--a2ui-text-primary);
    }

    /* ── Empty hint ────────────────────────────────────── */

    .empty-hint {
      display: flex;
      align-items: center;
      padding: 0 var(--a2ui-space-3);
      font-size: var(--a2ui-text-xs);
      color: var(--a2ui-text-tertiary);
      white-space: nowrap;
      flex-shrink: 0;
    }

    /* ── Responsive: Tablet (≤768px) ──────────────────── */

    @media (max-width: 768px) {
      .tab-bar {
        height: 32px;
        padding: 0 var(--a2ui-space-1);
      }

      .tab {
        max-width: 160px;
        font-size: 11px;
      }
    }

    /* ── Responsive: Mobile (≤480px) ─────────────────── */

    @media (max-width: 480px) {
      .tab-bar {
        height: 30px;
        gap: 1px;
      }

      .new-btn {
        width: 24px;
        height: 24px;
        margin-right: 2px;
      }

      .new-btn svg {
        width: 16px;
        height: 16px;
      }

      .bar-divider {
        height: 12px;
      }

      .tab {
        max-width: 120px;
        height: 22px;
        padding: 0 3px 0 6px;
        font-size: 10px;
        border-radius: 4px;
      }

      /* Always show close button on mobile (no hover on touch) */
      .tab .tab-close {
        opacity: 0.5;
      }

      .rename-input {
        width: 80px;
        font-size: 10px;
      }
    }
  `;

  @property({ type: Array }) threads: ChatThread[] = [];
  @property({ type: String }) activeThreadId: string | null = null;

  /** ID of the thread currently being renamed (inline edit). */
  @state() private renamingId: string | null = null;
  @state() private renameValue = '';

  // ── Event dispatchers ─────────────────────────────────

  private emitNewChat() {
    this.dispatchEvent(new CustomEvent('new-chat', { bubbles: true, composed: true }));
  }

  private emitSwitchThread(threadId: string) {
    this.dispatchEvent(new CustomEvent('switch-thread', {
      detail: { threadId },
      bubbles: true,
      composed: true,
    }));
  }

  private emitDeleteThread(threadId: string, e: Event) {
    e.stopPropagation(); // Don't trigger switch
    this.dispatchEvent(new CustomEvent('delete-thread', {
      detail: { threadId },
      bubbles: true,
      composed: true,
    }));
  }

  private emitRenameThread(threadId: string, title: string) {
    this.dispatchEvent(new CustomEvent('rename-thread', {
      detail: { threadId, title },
      bubbles: true,
      composed: true,
    }));
  }

  // ── Inline rename ─────────────────────────────────────

  private startRename(threadId: string, currentTitle: string, e: Event) {
    e.stopPropagation();
    this.renamingId = threadId;
    this.renameValue = currentTitle;
  }

  private handleRenameKeydown(threadId: string, e: KeyboardEvent) {
    if (e.key === 'Enter') {
      this.commitRename(threadId);
    } else if (e.key === 'Escape') {
      this.renamingId = null;
    }
  }

  private handleRenameBlur(threadId: string) {
    this.commitRename(threadId);
  }

  private commitRename(threadId: string) {
    const trimmed = this.renameValue.trim();
    if (trimmed && this.renamingId === threadId) {
      this.emitRenameThread(threadId, trimmed);
    }
    this.renamingId = null;
  }

  // ── Render ────────────────────────────────────────────

  render() {
    // Don't render the bar at all if there are no threads and no active chat
    if (this.threads.length === 0 && !this.activeThreadId) {
      return nothing;
    }

    return html`
      <div class="tab-bar" role="tablist" aria-label="Chat threads">
        <!-- New chat button -->
        <button
          class="new-btn"
          @click=${this.emitNewChat}
          title="New chat"
          aria-label="New chat"
        >
          <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/>
          </svg>
        </button>

        <!-- Thread tabs -->
        ${this.threads.map(thread => {
          const isActive = thread.id === this.activeThreadId;
          const isRenaming = this.renamingId === thread.id;

          return html`
            <button
              class="tab ${isActive ? 'active' : ''}"
              role="tab"
              aria-selected=${isActive}
              @click=${() => this.emitSwitchThread(thread.id)}
              @dblclick=${(e: Event) => this.startRename(thread.id, thread.title, e)}
              title=${thread.title}
            >
              ${isRenaming ? html`
                <input
                  class="rename-input"
                  aria-label="Rename thread"
                  .value=${this.renameValue}
                  @input=${(e: InputEvent) => { this.renameValue = (e.target as HTMLInputElement).value; }}
                  @keydown=${(e: KeyboardEvent) => this.handleRenameKeydown(thread.id, e)}
                  @blur=${() => this.handleRenameBlur(thread.id)}
                  @click=${(e: Event) => e.stopPropagation()}
                />
              ` : html`
                <span class="tab-title">${thread.title}</span>
              `}

              <span
                class="tab-close"
                role="button"
                tabindex="-1"
                @click=${(e: Event) => this.emitDeleteThread(thread.id, e)}
                aria-label="Close thread"
                title="Close thread"
              ><svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg></span>
            </button>
          `;
        })}
      </div>
    `;
  }

  /** After rendering, auto-focus the rename input. */
  updated(changed: Map<string, unknown>) {
    if (changed.has('renamingId') && this.renamingId) {
      const input = this.shadowRoot?.querySelector('.rename-input') as HTMLInputElement | null;
      if (input) {
        input.focus();
        input.select();
      }
    }
  }
}
