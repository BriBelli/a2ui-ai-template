import { LitElement, html, css } from 'lit';
import { customElement, property, query } from 'lit/decorators.js';
import type { ChatMessage } from '../../services/chat-service';
import { uiConfig, type LoadingStyle } from '../../config/ui-config';

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
    }

    .messages-wrapper {
      max-width: var(--a2ui-chat-max-width);
      margin: 0 auto;
      padding: 0 var(--a2ui-space-4);
    }

    .welcome {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      height: 100%;
      text-align: center;
      padding: var(--a2ui-space-8);
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
      margin-bottom: var(--a2ui-space-3);
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
      margin-top: var(--a2ui-space-6);
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
      transition: all 0.2s cubic-bezier(0.22, 1, 0.36, 1);
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

    /* ========== Loading Styles ========== */

    /* Base loading animation */
    .loading {
      animation: loadingIn 0.3s cubic-bezier(0.22, 1, 0.36, 1) forwards;
    }

    @keyframes loadingIn {
      from {
        opacity: 0;
        transform: translateY(8px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }

    /* --- Subtle Loading Style --- */
    .loading.subtle {
      display: flex;
      align-items: center;
      gap: var(--a2ui-space-2);
      padding: var(--a2ui-space-4);
      color: var(--a2ui-text-secondary);
      font-size: var(--a2ui-text-sm);
    }

    .loading.subtle .loading-dots {
      display: flex;
      gap: 4px;
    }

    .loading.subtle .loading-dot {
      width: 6px;
      height: 6px;
      background: var(--a2ui-accent);
      border-radius: 50%;
      animation: bounce 1.4s infinite ease-in-out both;
    }

    .loading.subtle .loading-dot:nth-child(1) { animation-delay: -0.32s; }
    .loading.subtle .loading-dot:nth-child(2) { animation-delay: -0.16s; }
    .loading.subtle .loading-dot:nth-child(3) { animation-delay: 0; }

    @keyframes bounce {
      0%, 80%, 100% { transform: scale(0); }
      40% { transform: scale(1); }
    }

    /* --- Chat Loading Style --- */
    .loading.chat {
      display: flex;
      align-items: flex-start;
      gap: var(--a2ui-space-3);
      padding: var(--a2ui-space-4) 0;
    }

    .loading-avatar {
      width: 32px;
      height: 32px;
      border-radius: var(--a2ui-radius-full);
      background: linear-gradient(135deg, #4285f4, #ea4335, #fbbc05, #34a853);
      display: flex;
      align-items: center;
      justify-content: center;
      color: white;
      font-size: var(--a2ui-text-sm);
      font-weight: var(--a2ui-font-medium);
      flex-shrink: 0;
    }

    .loading-content {
      display: flex;
      align-items: center;
      gap: var(--a2ui-space-2);
      padding: var(--a2ui-space-3) var(--a2ui-space-4);
      background: var(--a2ui-bg-secondary);
      border-radius: var(--a2ui-radius-xl);
      border-bottom-left-radius: var(--a2ui-radius-sm);
    }

    .loading.chat .loading-dots {
      display: flex;
      gap: 4px;
      align-items: center;
    }

    .loading.chat .loading-dot {
      width: 8px;
      height: 8px;
      background: var(--a2ui-text-tertiary);
      border-radius: 50%;
      animation: pulse 1.4s infinite ease-in-out;
    }

    .loading.chat .loading-dot:nth-child(1) { animation-delay: 0s; }
    .loading.chat .loading-dot:nth-child(2) { animation-delay: 0.2s; }
    .loading.chat .loading-dot:nth-child(3) { animation-delay: 0.4s; }

    @keyframes pulse {
      0%, 60%, 100% {
        opacity: 0.3;
        transform: scale(0.8);
      }
      30% {
        opacity: 1;
        transform: scale(1);
      }
    }

    .loading-text {
      color: var(--a2ui-text-secondary);
      font-size: var(--a2ui-text-sm);
      margin-left: var(--a2ui-space-1);
    }
  `;

  @property({ type: Array }) messages: ChatMessage[] = [];
  @property({ type: Boolean }) isLoading = false;
  @property({ type: String, attribute: 'loading-style' }) loadingStyle: LoadingStyle = uiConfig.loadingStyle;

  @query('.messages-container') private messagesContainer!: HTMLElement;

  private suggestions = [
    'Compare iPhone vs Android',
    'Top 5 trending stocks',
    'Show weather forecast',
    'Explain machine learning',
    'Create a task list',
  ];

  connectedCallback() {
    super.connectedCallback();
    // Apply animation attributes from config
    if (uiConfig.animateWelcome) {
      this.setAttribute('animate-welcome', '');
    }
  }

  updated(changedProperties: Map<string, unknown>) {
    if (changedProperties.has('messages')) {
      this.scrollToBottom();
    }
  }

  private scrollToBottom() {
    requestAnimationFrame(() => {
      if (this.messagesContainer) {
        this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
      }
    });
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
    const style = this.loadingStyle;

    if (style === 'chat') {
      return html`
        <div class="loading chat">
          <div class="loading-avatar">AI</div>
          <div class="loading-content">
            <div class="loading-dots">
              <div class="loading-dot"></div>
              <div class="loading-dot"></div>
              <div class="loading-dot"></div>
            </div>
            <span class="loading-text">Thinking</span>
          </div>
        </div>
      `;
    }

    // Subtle style (default fallback)
    return html`
      <div class="loading subtle">
        <div class="loading-dots">
          <div class="loading-dot"></div>
          <div class="loading-dot"></div>
          <div class="loading-dot"></div>
        </div>
        <span>Thinking...</span>
      </div>
    `;
  }

  render() {
    const hasMessages = this.messages.length > 0;

    return html`
      <div class="messages-container">
        ${hasMessages ? html`
          <div class="messages-wrapper">
            ${this.messages.map(msg => html`
              <a2ui-chat-message
                .message=${msg}
              ></a2ui-chat-message>
            `)}
            ${this.isLoading ? this.renderLoading() : ''}
          </div>
        ` : html`
          <div class="welcome">
            <h1 class="welcome-title">Hello! How can I help you today?</h1>
            <p class="welcome-subtitle">
              Ask me anything. I can search the web, analyze data, create charts, and more.
            </p>
            <div class="suggestions">
              ${this.suggestions.map(s => html`
                <button class="suggestion" @click=${() => this.handleSuggestionClick(s)}>
                  ${s}
                </button>
              `)}
            </div>
          </div>
        `}
      </div>
      
      <div class="input-container">
        <div class="input-wrapper">
          <a2ui-chat-input
            ?disabled=${this.isLoading}
            @send-message=${this.handleSendMessage}
          ></a2ui-chat-input>
        </div>
      </div>
    `;
  }
}
