import { LitElement, html, css } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import type { ChatMessage } from '../../services/chat-service';
import { A2UIRenderer } from '../../services/a2ui-renderer';
import { uiConfig } from '../../config/ui-config';

@customElement('a2ui-chat-message')
export class A2UIChatMessage extends LitElement {
  static styles = css`
    :host {
      display: block;
      margin-bottom: var(--a2ui-space-6);
    }

    /* Message entrance animation (when enabled) */
    :host([animate]) {
      animation: messageIn 0.3s cubic-bezier(0.22, 1, 0.36, 1) forwards;
      opacity: 0;
    }

    @keyframes messageIn {
      from {
        opacity: 0;
        transform: translateY(12px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }

    .message {
      display: flex;
      gap: var(--a2ui-space-3);
    }

    .message.user {
      flex-direction: row-reverse;
    }

    .avatar {
      width: 32px;
      height: 32px;
      border-radius: var(--a2ui-radius-full);
      flex-shrink: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: var(--a2ui-text-sm);
      font-weight: var(--a2ui-font-medium);
      transition: transform 0.2s ease;
    }

    .avatar:hover {
      transform: scale(1.05);
    }

    .avatar.user {
      background: var(--a2ui-accent);
      color: var(--a2ui-text-inverse);
      overflow: hidden;
    }

    .avatar.user img {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }

    .avatar.assistant {
      background: linear-gradient(135deg, #4285f4, #ea4335, #fbbc05, #34a853);
      color: white;
    }

    .content {
      flex: 1;
      min-width: 0;
    }

    .user .content {
      display: flex;
      flex-direction: column;
      align-items: flex-end;
    }

    .bubble {
      padding: var(--a2ui-space-3) var(--a2ui-space-4);
      border-radius: var(--a2ui-radius-xl);
      max-width: 100%;
      transition: box-shadow 0.15s ease;
    }

    .bubble:hover {
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
    }

    .user .bubble {
      background: var(--a2ui-accent);
      color: var(--a2ui-text-inverse);
      border-bottom-right-radius: var(--a2ui-radius-sm);
    }

    .assistant .bubble {
      background: var(--a2ui-bg-secondary);
      color: var(--a2ui-text-primary);
      border-bottom-left-radius: var(--a2ui-radius-sm);
    }

    .text-content {
      white-space: pre-wrap;
      word-break: break-word;
      line-height: var(--a2ui-leading-relaxed);
    }

    .a2ui-content {
      margin-top: var(--a2ui-space-3);
    }

    /* A2UI content fade-in (when animated) */
    :host([animate]) .a2ui-content {
      animation: contentFadeIn 0.4s ease 0.15s forwards;
      opacity: 0;
    }

    @keyframes contentFadeIn {
      from { opacity: 0; }
      to { opacity: 1; }
    }

    .meta {
      display: flex;
      align-items: center;
      gap: var(--a2ui-space-2);
      margin-top: var(--a2ui-space-1);
      font-size: var(--a2ui-text-xs);
      color: var(--a2ui-text-tertiary);
    }

    /* Meta fade-in (when animated) */
    :host([animate]) .meta {
      animation: metaFadeIn 0.3s ease 0.2s forwards;
      opacity: 0;
    }

    @keyframes metaFadeIn {
      from { opacity: 0; }
      to { opacity: 1; }
    }

    .user .meta {
      justify-content: flex-end;
    }

    .model-badge {
      display: inline-flex;
      align-items: center;
      gap: var(--a2ui-space-1);
      padding: 2px 6px;
      background: var(--a2ui-bg-tertiary);
      border-radius: var(--a2ui-radius-sm);
      font-size: 10px;
      transition: background-color 0.15s ease;
    }

    .model-badge:hover {
      background: var(--a2ui-bg-elevated);
    }
  `;

  @property({ type: Object }) message!: ChatMessage;

  connectedCallback() {
    super.connectedCallback();
    // Apply animation attribute from config
    if (uiConfig.animateMessages) {
      this.setAttribute('animate', '');
    }
  }

  private formatTime(timestamp: number): string {
    return new Date(timestamp).toLocaleTimeString([], { 
      hour: '2-digit', 
      minute: '2-digit' 
    });
  }

  render() {
    const { role, content, a2ui, timestamp, model } = this.message;
    const isUser = role === 'user';

    return html`
      <div class="message ${role}">
        <div class="avatar ${role}">
          ${isUser
            ? (this.message.avatarUrl
                ? html`<img src=${this.message.avatarUrl} alt="" />`
                : (this.message.avatarInitials || 'U'))
            : 'AI'}
        </div>
        <div class="content">
          ${isUser ? html`
            <div class="bubble">
              <div class="text-content">${content}</div>
            </div>
          ` : html`
            <div class="bubble">
              ${content ? html`
                <div class="text-content">${content}</div>
              ` : ''}
              ${a2ui ? html`
                <div class="a2ui-content">
                  ${A2UIRenderer.render(a2ui)}
                </div>
              ` : ''}
            </div>
          `}
          <div class="meta">
            ${!isUser && model ? html`
              <span class="model-badge">✨ ${model}</span>
            ` : ''}
            <span>${this.formatTime(timestamp)}</span>
          </div>
        </div>
      </div>
    `;
  }
}
