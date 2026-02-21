import { LitElement, html, css } from 'lit';
import { customElement, property, query, state } from 'lit/decorators.js';

@customElement('a2ui-chat-input')
export class A2UIChatInput extends LitElement {
  static styles = css`
    :host {
      display: block;
    }

    .input-container {
      display: flex;
      align-items: flex-end;
      gap: var(--a2ui-space-2);
      padding: var(--a2ui-space-3);
      background: var(--a2ui-bg-input);
      border: 1px solid var(--a2ui-border-default);
      border-radius: var(--a2ui-radius-2xl);
      transition: border-color var(--a2ui-transition-fast);
      position: relative;
    }

    .input-container:focus-within {
      background: var(--a2ui-bg-input-focus);
      border-color: var(--a2ui-accent);
      outline: 2px solid var(--a2ui-accent-subtle);
      outline-offset: -1px;
    }

    .input-container.disabled {
      opacity: 0.6;
      pointer-events: none;
    }

    textarea {
      flex: 1;
      background: none;
      border: none;
      outline: none;
      color: var(--a2ui-text-primary);
      font-family: var(--a2ui-font-family);
      font-size: var(--a2ui-text-md);
      line-height: var(--a2ui-leading-normal);
      resize: none;
      max-height: 200px;
      padding: var(--a2ui-space-1) 0;
      overflow-y: hidden;
    }

    textarea::placeholder {
      color: var(--a2ui-text-tertiary);
    }

    .send-button {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 40px;
      height: 40px;
      background: var(--a2ui-accent);
      border: none;
      border-radius: var(--a2ui-radius-full);
      color: var(--a2ui-text-inverse);
      cursor: pointer;
      transition: transform var(--a2ui-transition-fast);
      flex-shrink: 0;
      position: absolute;
      right: 6px;
      top: 6px;
    }

    .send-button:hover {
      background: var(--a2ui-accent-hover);
      transform: scale(1.05);
    }

    .send-button:active {
      background: var(--a2ui-accent-active);
      transform: scale(0.95);
    }

    .send-button:disabled {
      background: var(--a2ui-bg-tertiary);
      cursor: not-allowed;
      transform: none;
    }

    .send-icon {
      width: 20px;
      height: 20px;
    }

    /* ── Responsive: Tablet (≤768px) ──────────────────── */

    @media (max-width: 768px) {
      .input-container {
        padding: var(--a2ui-space-2) var(--a2ui-space-3);
      }

      textarea {
        font-size: 16px; /* Prevent iOS auto-zoom on focus */
      }
    }

    /* ── Responsive: Mobile (≤480px) ─────────────────── */

    @media (max-width: 480px) {
      .input-container {
        padding: var(--a2ui-space-2);
        border-radius: var(--a2ui-radius-xl);
      }

      textarea {
        font-size: 16px; /* Prevent iOS auto-zoom on focus */
        max-height: 120px;
      }

      .send-button {
        width: 34px;
        height: 34px;
        right: 4px;
        top: 4px;
      }

      .send-icon {
        width: 18px;
        height: 18px;
      }
    }
  `;

  @property({ type: Boolean }) disabled = false;
  @state() private value = '';

  @query('textarea') private textarea!: HTMLTextAreaElement;
  private baselineHeight = 0;

  private handleInput(e: Event) {
    const target = e.target as HTMLTextAreaElement;
    this.value = target.value;
    this.autoResize(target);
  }

  private autoResize(textarea: HTMLTextAreaElement) {
    if (!this.baselineHeight) {
      this.baselineHeight = textarea.offsetHeight;
    }
    textarea.style.height = 'auto';
    const newHeight = Math.max(this.baselineHeight, Math.min(textarea.scrollHeight, 200));
    textarea.style.height = newHeight + 'px';
  }

  private handleKeyDown(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      this.sendMessage();
    }
  }

  private sendMessage() {
    if (!this.value.trim() || this.disabled) return;

    this.dispatchEvent(new CustomEvent('send-message', {
      detail: { message: this.value.trim() },
      bubbles: true,
      composed: true,
    }));

    this.value = '';
    if (this.textarea) {
      this.textarea.style.height = 'auto';
    }
  }

  render() {
    return html`
      <div class="input-container ${this.disabled ? 'disabled' : ''}" role="group" aria-label="Message composer">
        <textarea
          rows="1"
          placeholder="Ask me anything..."
          aria-label="Message input"
          .value=${this.value}
          ?disabled=${this.disabled}
          @input=${this.handleInput}
          @keydown=${this.handleKeyDown}
        ></textarea>
        <button 
          class="send-button"
          aria-label="Send message"
          ?disabled=${!this.value.trim() || this.disabled}
          @click=${this.sendMessage}
        >
          <svg class="send-icon" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
          </svg>
        </button>
      </div>
    `;
  }
}
