import { LitElement, html, css } from 'lit';
import { customElement, property, query } from 'lit/decorators.js';
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
  `;

  @property({ type: Array }) messages: ChatMessage[] = [];
  @property({ type: Boolean }) isLoading = false;
  @property({ type: Array }) suggestions: string[] = [];
  @property({ type: Array }) thinkingSteps: ThinkingStep[] = [];

  @query('.messages-container') private messagesContainer!: HTMLElement;

  connectedCallback() {
    super.connectedCallback();
    // Apply animation attributes from config
    if (uiConfig.animateWelcome) {
      this.setAttribute('animate-welcome', '');
    }
  }

  updated(changedProperties: Map<string, unknown>) {
    if (changedProperties.has('messages') || changedProperties.has('isLoading')) {
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
    return html`<a2ui-thinking-indicator .steps=${this.thinkingSteps}></a2ui-thinking-indicator>`;
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
