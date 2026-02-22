import { LitElement, html, css } from 'lit';
import { customElement, property, query, state } from 'lit/decorators.js';
import type { ChatMessage } from '../../services/chat-service';
import type { ThinkingStep } from './a2ui-thinking-indicator';
import { uiConfig } from '../../config/ui-config';

@customElement('a2ui-chat-container')
export class A2UIChatContainer extends LitElement {
  static styles = css`
    :host {
      display: flex;
      flex-direction: column;
      height: 100%;
      background: var(--a2ui-bg-app);
    }

    .messages-container {
      flex: 1;
      overflow-y: auto;
      padding: var(--a2ui-space-6) 0;
      scroll-behavior: smooth;
    }

    .messages-wrapper {
      max-width: var(--a2ui-chat-max-width);
      margin: 0 auto;
      padding: 0 var(--a2ui-space-4);
      transition: max-width 0.3s ease;
    }

    .messages-wrapper.expanded {
      max-width: var(--a2ui-chat-max-width-expanded);
    }

    .welcome {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      height: 100%;
      text-align: center;
      padding: 0;
    }

    /* Welcome animations (when enabled) */
    :host([animate-welcome]) .welcome-title {
      animation: welcomeFadeIn 0.5s cubic-bezier(0.22, 1, 0.36, 1) forwards;
      opacity: 0;
    }

    :host([animate-welcome]) .welcome-subtitle {
      animation: welcomeFadeIn 0.5s cubic-bezier(0.22, 1, 0.36, 1) 0.1s forwards;
      opacity: 0;
    }

    @keyframes welcomeFadeIn {
      from {
        opacity: 0;
        transform: translateY(10px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }

    .welcome-title {
      font-size: var(--a2ui-text-3xl);
      font-weight: var(--a2ui-font-medium);
      color: var(--a2ui-text-primary);
      margin-bottom: var(--a2ui-space-0);
    }

    .welcome-subtitle {
      font-size: var(--a2ui-text-lg);
      color: var(--a2ui-text-secondary);
      max-width: 500px;
    }

    .suggestions {
      display: flex;
      flex-wrap: wrap;
      gap: var(--a2ui-space-2);
      margin-top: var(--a2ui-space-3);
      justify-content: center;
    }

    .suggestion {
      padding: var(--a2ui-space-2) var(--a2ui-space-4);
      background: var(--a2ui-bg-secondary);
      border: 1px solid var(--a2ui-border-default);
      border-radius: var(--a2ui-radius-full);
      color: var(--a2ui-text-primary);
      font-size: var(--a2ui-text-sm);
      font-family: var(--a2ui-font-family);
      cursor: pointer;
      transition: border-color 0.2s cubic-bezier(0.22, 1, 0.36, 1), transform 0.2s cubic-bezier(0.22, 1, 0.36, 1);
    }

    /* Suggestion animations (when enabled) */
    :host([animate-welcome]) .suggestion {
      animation: chipIn 0.4s cubic-bezier(0.22, 1, 0.36, 1) backwards;
    }

    :host([animate-welcome]) .suggestion:nth-child(1) { animation-delay: 0.1s; }
    :host([animate-welcome]) .suggestion:nth-child(2) { animation-delay: 0.15s; }
    :host([animate-welcome]) .suggestion:nth-child(3) { animation-delay: 0.2s; }
    :host([animate-welcome]) .suggestion:nth-child(4) { animation-delay: 0.25s; }
    :host([animate-welcome]) .suggestion:nth-child(5) { animation-delay: 0.3s; }

    @keyframes chipIn {
      from {
        opacity: 0;
        transform: translateY(8px) scale(0.95);
      }
      to {
        opacity: 1;
        transform: translateY(0) scale(1);
      }
    }

    .suggestion:hover {
      background: var(--a2ui-bg-tertiary);
      border-color: var(--a2ui-accent);
      transform: translateY(-2px);
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    }

    .suggestion:active {
      transform: translateY(0) scale(0.98);
    }

    .input-container {
      padding: var(--a2ui-space-4);
      background: var(--a2ui-bg-primary);
      border-top: 1px solid var(--a2ui-border-subtle);
    }

    .input-wrapper {
      max-width: var(--a2ui-chat-max-width);
      margin: 0 auto;
    }

    /* Thinking indicator slot */
    a2ui-thinking-indicator {
      margin-bottom: var(--a2ui-space-4);
    }

    /* Scroll-to-bottom FAB */
      /* Visually hidden but accessible to screen readers */
    .sr-only {
      position: absolute;
      width: 1px;
      height: 1px;
      padding: 0;
      margin: -1px;
      overflow: hidden;
      clip: rect(0, 0, 0, 0);
      white-space: nowrap;
      border: 0;
    }

    .scroll-fab {
      position: absolute;
      bottom: var(--a2ui-space-2);
      left: 50%;
      transform: translateX(-50%) translateY(8px) scale(0.9);
      opacity: 0;
      pointer-events: none;
      width: 36px;
      height: 36px;
      border-radius: 50%;
      background: var(--a2ui-bg-secondary);
      border: 1px solid var(--a2ui-border-default);
      color: var(--a2ui-text-secondary);
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: var(--a2ui-shadow-md);
      transition: opacity 0.2s ease, transform 0.2s ease, background-color 0.15s ease;
      z-index: 10;
    }

    .scroll-fab.visible {
      opacity: 1;
      pointer-events: auto;
      transform: translateX(-50%) translateY(0) scale(1);
    }

    .scroll-fab:hover {
      background: var(--a2ui-bg-tertiary);
      color: var(--a2ui-text-primary);
      border-color: var(--a2ui-accent);
    }

    .messages-area {
      position: relative;
      flex: 1;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }

    /* ── Responsive: Tablet (≤768px) ──────────────────── */

    @media (max-width: 768px) {
      .messages-container {
        padding: var(--a2ui-space-4) 0;
      }

      .messages-wrapper {
        padding: 0 var(--a2ui-space-3);
      }

      .welcome {
        padding: var(--a2ui-space-6);
      }

      .welcome-title {
        font-size: var(--a2ui-text-2xl);
      }

      .welcome-subtitle {
        font-size: var(--a2ui-text-md);
        max-width: 400px;
      }

      .input-container {
        padding: var(--a2ui-space-3);
      }
    }

    /* ── Responsive: Mobile (≤480px) ─────────────────── */

    @media (max-width: 480px) {
      .messages-container {
        padding: var(--a2ui-space-3) 0;
      }

      .messages-wrapper {
        padding: 0 var(--a2ui-space-2);
      }

      .welcome {
        padding: var(--a2ui-space-4) var(--a2ui-space-3);
        justify-content: flex-start;
        padding-top: 20vh;
      }

      .welcome-title {
        font-size: var(--a2ui-text-xl);
      }

      .welcome-subtitle {
        font-size: var(--a2ui-text-sm);
        max-width: 300px;
      }

      .suggestions {
        margin-top: var(--a2ui-space-4);
        gap: var(--a2ui-space-1);
      }

      .suggestion {
        padding: var(--a2ui-space-1) var(--a2ui-space-3);
        font-size: var(--a2ui-text-xs);
      }

      .input-container {
        padding: var(--a2ui-space-2);
      }

      .scroll-fab {
        width: 32px;
        height: 32px;
      }
    }
  `;

  @property({ type: Array }) messages: ChatMessage[] = [];
  @property({ type: Boolean }) isLoading = false;
  @property({ type: Array }) suggestions: string[] = [];
  @property({ type: Array }) thinkingSteps: ThinkingStep[] = [];
  @property({ type: String }) loadingDisplay: string = 'moderate';

  /** Screen-reader announcement text for new messages */
  @state() private srAnnouncement = '';

  @query('.messages-container') private messagesContainer!: HTMLElement;

  /** True when the user hasn't scrolled far from the bottom */
  private _userNearBottom = true;
  private _showScrollFab = false;

  connectedCallback() {
    super.connectedCallback();
    if (uiConfig.animateWelcome) {
      this.setAttribute('animate-welcome', '');
    }
  }

  firstUpdated() {
    // Listen for scroll events on the messages container
    this.messagesContainer?.addEventListener('scroll', this._onScroll, { passive: true });
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    this.messagesContainer?.removeEventListener('scroll', this._onScroll);
  }

  private _onScroll = () => {
    const el = this.messagesContainer;
    if (!el) return;
    const threshold = 120; // px from bottom
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < threshold;
    this._userNearBottom = nearBottom;

    // Show/hide the FAB — only when there's meaningful scroll distance
    const scrollRemaining = el.scrollHeight - el.scrollTop - el.clientHeight;
    const shouldShow = scrollRemaining > 300;
    if (shouldShow !== this._showScrollFab) {
      this._showScrollFab = shouldShow;
      const fab = this.shadowRoot?.querySelector('.scroll-fab');
      fab?.classList.toggle('visible', shouldShow);
    }
  };

  updated(changedProperties: Map<string, unknown>) {
    if (changedProperties.has('messages') || changedProperties.has('isLoading')) {
      if (this._userNearBottom) {
        this._scrollToLastUserMessage();
      } else if (changedProperties.has('messages')) {
        const prev = changedProperties.get('messages') as ChatMessage[] | undefined;
        if (prev && this.messages.length > prev.length) {
          const lastNew = this.messages[this.messages.length - 1];
          if (lastNew.role === 'user') {
            this._scrollToLastUserMessage();
          }
        }
      }

      // Screen-reader announcement for new messages
      if (changedProperties.has('messages')) {
        const prev = changedProperties.get('messages') as ChatMessage[] | undefined;
        if (prev && this.messages.length > prev.length) {
          const lastMsg = this.messages[this.messages.length - 1];
          if (lastMsg.role === 'assistant') {
            const text = lastMsg.content || 'New response received';
            // Truncate long responses for the announcement
            this.srAnnouncement = text.length > 200
              ? `Assistant responded: ${text.slice(0, 200)}...`
              : `Assistant responded: ${text}`;
          } else if (lastMsg.role === 'user') {
            this.srAnnouncement = 'Message sent';
          }
        }
      }
    }

    // Announce loading state changes
    if (changedProperties.has('isLoading')) {
      if (this.isLoading) {
        this.srAnnouncement = 'Generating response, please wait...';
      }
    }
  }

  private _scrollToLastUserMessage() {
    requestAnimationFrame(() => {
      const el = this.messagesContainer;
      if (!el) return;

      const messageElements = el.querySelectorAll('a2ui-chat-message');
      let lastUserEl: Element | null = null;

      for (let i = this.messages.length - 1; i >= 0; i--) {
        if (this.messages[i].role === 'user' && messageElements[i]) {
          lastUserEl = messageElements[i];
          break;
        }
      }

      if (lastUserEl) {
        const containerTop = el.getBoundingClientRect().top;
        const msgTop = lastUserEl.getBoundingClientRect().top;
        const offset = msgTop - containerTop + el.scrollTop;
        el.scrollTo({ top: Math.max(0, offset - 8), behavior: 'smooth' });
      } else {
        el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
      }
    });
  }

  private scrollToBottom() {
    requestAnimationFrame(() => {
      const el = this.messagesContainer;
      if (!el) return;
      el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
      this._userNearBottom = true;
    });
  }

  private _handleScrollFabClick() {
    this.scrollToBottom();
  }

  private handleSuggestionClick(suggestion: string) {
    this.dispatchEvent(new CustomEvent('send-message', {
      detail: { message: suggestion },
      bubbles: true,
      composed: true,
    }));
  }

  private handleSendMessage(e: CustomEvent<{ message: string }>) {
    // Stop the original event from bubbling further to prevent double-dispatch
    e.stopPropagation();
    
    this.dispatchEvent(new CustomEvent('send-message', {
      detail: e.detail,
      bubbles: true,
      composed: true,
    }));
  }

  private renderLoading() {
    return html`<a2ui-thinking-indicator .steps=${this.thinkingSteps} .displayLevel=${this.loadingDisplay}></a2ui-thinking-indicator>`;
  }

  private get _hasSources(): boolean {
    return uiConfig.showSources && uiConfig.sourcesPosition !== 'bottom' &&
      this.messages.some(m => m.role === 'assistant' && m.sources?.length);
  }

  render() {
    const hasMessages = this.messages.length > 0;

    return html`
      <div class="messages-area">
        <div class="messages-container">
          ${hasMessages ? html`
            <div class="messages-wrapper ${this._hasSources ? 'expanded' : ''}" role="log" aria-label="Chat messages" aria-live="polite">
              ${this.messages.map((msg, idx) => html`
                <a2ui-chat-message
                  .message=${msg}
                  .editable=${msg.role === 'user' && !this.isLoading}
                  .isLast=${msg.role === 'assistant' && idx === this.messages.length - 1 && !this.isLoading}
                ></a2ui-chat-message>
              `)}
              ${this.isLoading ? this.renderLoading() : ''}
            </div>
          ` : html`
            <div class="welcome">
              <h1 class="welcome-title">How can I help you today?</h1>
              <p class="welcome-subtitle">
                I can search the web, analyze data, create charts, and more.
              </p>
              ${uiConfig.maxSuggestions > 0 && this.suggestions.length > 0 ? html`
                <div class="suggestions">
                  ${this.suggestions.slice(0, uiConfig.maxSuggestions).map(s => html`
                    <button class="suggestion" @click=${() => this.handleSuggestionClick(s)}>
                      ${s}
                    </button>
                  `)}
                </div>
              ` : ''}
            </div>
          `}
        </div>

        <!-- Scroll-to-bottom FAB (appears when user scrolls up) -->
        <button class="scroll-fab" @click=${this._handleScrollFabClick} title="Scroll to bottom" aria-label="Scroll to bottom">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <path d="M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6z"/>
          </svg>
        </button>
      </div>
      
      <div class="input-container">
        <div class="input-wrapper">
          <a2ui-chat-input
            ?disabled=${this.isLoading}
            @send-message=${this.handleSendMessage}
          ></a2ui-chat-input>
        </div>
      </div>

      <!-- Screen reader announcements for chat activity -->
      <div class="sr-only" role="status" aria-live="polite" aria-atomic="true">
        ${this.srAnnouncement}
      </div>
    `;
  }
}
