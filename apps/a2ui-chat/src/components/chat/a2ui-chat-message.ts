import { LitElement, html, css, unsafeCSS, nothing } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import type { ChatMessage } from '../../services/chat-service';
import { A2UIRenderer } from '../../services/a2ui-renderer';
import { uiConfig } from '../../config/ui-config';
import { md, markdownStyles } from '../../services/markdown';

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
      max-width: 100%;
    }

    .user .bubble {
      padding: var(--a2ui-space-3) var(--a2ui-space-4);
      background: var(--a2ui-accent);
      color: var(--a2ui-text-inverse);
      border-radius: var(--a2ui-radius-xl);
      border-bottom-right-radius: var(--a2ui-radius-sm);
      transition: box-shadow 0.15s ease;
    }

    .user .bubble:hover {
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
    }

    .assistant .bubble {
      color: var(--a2ui-text-primary);
    }

    .text-content {
      white-space: pre-wrap;
      word-break: break-word;
      line-height: var(--a2ui-leading-relaxed);
    }

    .assistant .text-content {
      white-space: normal;
      padding: var(--a2ui-space-1) 0;
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

    .duration, .style-badge {
      text-transform: capitalize;
      color: var(--a2ui-text-tertiary);
    }

    /* ── Edit mode ────────────────────────────────────── */

    .user .bubble {
      cursor: default;
    }

    .user .bubble.editable {
      cursor: pointer;
    }

    .edit-container {
      display: flex;
      flex-direction: column;
      gap: var(--a2ui-space-2);
      width: 100%;
      max-width: 600px;
    }

    .edit-textarea {
      width: 100%;
      min-height: 60px;
      max-height: 200px;
      padding: var(--a2ui-space-3) var(--a2ui-space-4);
      background: var(--a2ui-bg-primary);
      color: var(--a2ui-text-primary);
      border: 1.5px solid var(--a2ui-accent);
      border-radius: var(--a2ui-radius-xl);
      border-bottom-right-radius: var(--a2ui-radius-sm);
      font-family: var(--a2ui-font-family);
      font-size: var(--a2ui-text-base);
      line-height: var(--a2ui-leading-relaxed);
      resize: vertical;
      outline: none;
      box-sizing: border-box;
      transition: border-color 0.15s ease, box-shadow 0.15s ease;
    }

    .edit-textarea:focus {
      box-shadow: 0 0 0 3px rgba(66, 133, 244, 0.15);
    }

    .edit-actions {
      display: flex;
      gap: var(--a2ui-space-2);
      justify-content: flex-end;
    }

    .edit-btn {
      padding: var(--a2ui-space-1) var(--a2ui-space-3);
      border-radius: var(--a2ui-radius-md);
      border: none;
      font-family: var(--a2ui-font-family);
      font-size: var(--a2ui-text-sm);
      font-weight: var(--a2ui-font-medium);
      cursor: pointer;
      transition: background 0.15s ease, opacity 0.15s ease;
    }

    .edit-btn.cancel {
      background: var(--a2ui-bg-tertiary);
      color: var(--a2ui-text-secondary);
    }

    .edit-btn.cancel:hover {
      background: var(--a2ui-bg-elevated);
    }

    .edit-btn.submit {
      background: var(--a2ui-accent);
      color: var(--a2ui-text-inverse);
    }

    .edit-btn.submit:hover {
      opacity: 0.9;
    }

    .edit-btn.submit:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }

    /* ── Image strip ──────────────────────────────────── */

    .image-strip {
      display: flex;
      gap: var(--a2ui-space-2);
      margin-top: var(--a2ui-space-3);
      overflow-x: auto;
      padding-bottom: var(--a2ui-space-1);
      scrollbar-width: thin;
    }

    .image-strip::-webkit-scrollbar {
      height: 4px;
    }

    .image-strip::-webkit-scrollbar-track {
      background: transparent;
    }

    .image-strip::-webkit-scrollbar-thumb {
      background: var(--a2ui-border-default);
      border-radius: 2px;
    }

    .image-strip a {
      flex-shrink: 0;
      display: block;
      width: 160px;
      height: 110px;
      border-radius: var(--a2ui-radius-md);
      overflow: hidden;
      background: var(--a2ui-bg-tertiary);
      transition: opacity var(--a2ui-transition-fast),
                  transform var(--a2ui-transition-fast);
    }

    .image-strip a:hover {
      opacity: 0.85;
      transform: scale(1.02);
    }

    .image-strip img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
    }

    /* ── Follow-up suggestions ─────────────────────────── */

    .followups {
      display: flex;
      flex-direction: column;
      gap: var(--a2ui-space-2);
      margin-top: var(--a2ui-space-3);
    }

    .followup {
      display: flex;
      align-items: center;
      gap: var(--a2ui-space-2);
      background: none;
      border: none;
      padding: var(--a2ui-space-1) 0;
      color: var(--a2ui-text-secondary);
      font-size: var(--a2ui-text-sm);
      font-family: var(--a2ui-font-family);
      cursor: pointer;
      text-align: left;
      transition: color 0.15s ease;
    }

    .followup:hover {
      color: var(--a2ui-text-primary);
    }

    .followup-icon {
      flex-shrink: 0;
      width: 16px;
      height: 16px;
      color: var(--a2ui-text-tertiary);
    }

    /* ── Responsive: Tablet (≤768px) ──────────────────── */

    @media (max-width: 768px) {
      :host {
        margin-bottom: var(--a2ui-space-4);
      }

      .message {
        gap: var(--a2ui-space-2);
      }

      .avatar {
        width: 28px;
        height: 28px;
        font-size: var(--a2ui-text-xs);
      }
    }

    /* ── Responsive: Mobile (≤480px) ─────────────────── */

    @media (max-width: 480px) {
      :host {
        margin-bottom: var(--a2ui-space-3);
      }

      .message {
        gap: var(--a2ui-space-2);
      }

      .avatar {
        width: 24px;
        height: 24px;
        font-size: 10px;
      }

      .user .bubble {
        padding: var(--a2ui-space-2) var(--a2ui-space-3);
        border-radius: var(--a2ui-radius-lg);
        border-bottom-right-radius: var(--a2ui-radius-sm);
      }

      .text-content {
        font-size: var(--a2ui-text-sm);
        line-height: var(--a2ui-leading-normal);
      }

      .meta {
        font-size: 10px;
      }

      .model-badge {
        font-size: 9px;
        padding: 1px 4px;
      }

      .followup {
        font-size: var(--a2ui-text-xs);
        gap: var(--a2ui-space-1);
      }

      .followup-icon {
        width: 14px;
        height: 14px;
      }

      .followups {
        gap: var(--a2ui-space-1);
        margin-top: var(--a2ui-space-2);
      }

      .image-strip a {
        width: 120px;
        height: 85px;
      }
    }

    /* ── Markdown (assistant text) ─────────────── */
    ${unsafeCSS(markdownStyles)}
  `;

  @property({ type: Object }) message!: ChatMessage;
  @property({ type: Boolean }) editable = false;
  @state() private _editing = false;
  @state() private _editText = '';

  private _startEdit() {
    if (!this.editable || this.message.role !== 'user') return;
    this._editText = this.message.content;
    this._editing = true;
    this.requestUpdate();
    setTimeout(() => {
      const ta = this.shadowRoot?.querySelector<HTMLTextAreaElement>('.edit-textarea');
      if (ta) {
        ta.focus();
        ta.setSelectionRange(ta.value.length, ta.value.length);
        this._autoResize(ta);
      }
    }, 0);
  }

  private _cancelEdit() {
    this._editing = false;
  }

  private _submitEdit() {
    const trimmed = this._editText.trim();
    if (!trimmed || trimmed === this.message.content) {
      this._editing = false;
      return;
    }
    this._editing = false;
    this.dispatchEvent(new CustomEvent('edit-message', {
      detail: { messageId: this.message.id, newContent: trimmed },
      bubbles: true,
      composed: true,
    }));
  }

  private _handleEditKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      this._submitEdit();
    } else if (e.key === 'Escape') {
      this._cancelEdit();
    }
  }

  private _autoResize(el: HTMLTextAreaElement) {
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 200) + 'px';
  }

  private handleFollowup(text: string) {
    this.dispatchEvent(new CustomEvent('send-message', {
      detail: { message: text },
      bubbles: true,
      composed: true,
    }));
  }

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

  private _isSafeImageUrl(url: string): boolean {
    try {
      const parsed = new URL(url);
      return parsed.protocol === 'https:' || parsed.protocol === 'http:';
    } catch {
      return false;
    }
  }

  render() {
    const { role, content, a2ui, timestamp, model } = this.message;
    const isUser = role === 'user';

    return html`
      <div class="message ${role}" role="article" aria-label="${isUser ? 'User' : 'Assistant'} message">
        <div class="avatar ${role}" aria-hidden="true">
          ${isUser
            ? (this.message.avatarUrl
                ? html`<img src=${this.message.avatarUrl} alt="" />`
                : (this.message.avatarInitials || 'U'))
            : 'AI'}
        </div>
        <div class="content">
          ${isUser ? html`
            ${this._editing ? html`
              <div class="edit-container">
                <textarea
                  class="edit-textarea"
                  .value=${this._editText}
                  @input=${(e: InputEvent) => {
                    const ta = e.target as HTMLTextAreaElement;
                    this._editText = ta.value;
                    this._autoResize(ta);
                  }}
                  @keydown=${this._handleEditKeydown}
                ></textarea>
                <div class="edit-actions">
                  <button class="edit-btn cancel" @click=${this._cancelEdit}>Cancel</button>
                  <button
                    class="edit-btn submit"
                    ?disabled=${!this._editText.trim() || this._editText.trim() === content}
                    @click=${this._submitEdit}
                  >Send</button>
                </div>
              </div>
            ` : html`
              <div
                class="bubble ${this.editable ? 'editable' : ''}"
                @dblclick=${this.editable ? () => this._startEdit() : nothing}
                title=${this.editable ? 'Double-click to edit' : ''}
              >
                <div class="text-content">${content}</div>
              </div>
            `}
          ` : html`
            <div class="bubble">
              ${content ? html`
                <div class="text-content">${md(content)}</div>
              ` : ''}
              ${a2ui ? html`
                <div class="a2ui-content">
                  ${A2UIRenderer.render(a2ui)}
                </div>
              ` : ''}
            </div>
          `}
          ${!isUser && this.message.images?.length ? html`
            <div class="image-strip">
              ${this.message.images.filter(url => this._isSafeImageUrl(url)).map(url => html`
                <a href=${url} target="_blank" rel="noopener noreferrer">
                  <img src=${url} alt="" loading="lazy" @error=${(e: Event) => { (e.target as HTMLElement).parentElement!.style.display = 'none'; }} />
                </a>
              `)}
            </div>
          ` : ''}
          <div class="meta">
            ${!isUser && model ? html`
              <span class="model-badge">✨ ${model}</span>
            ` : ''}
            ${!isUser && this.message.duration ? html`
              <span class="duration">${this.message.duration}s</span>
            ` : ''}
            <span>${this.formatTime(timestamp)}</span>
            ${!isUser && this.message.style ? html`
              <span class="style-badge">${this.message.style.charAt(0).toUpperCase() + this.message.style.slice(1)}</span>
            ` : ''}
          </div>
          ${!isUser && uiConfig.maxSuggestions > 0 && this.message.suggestions?.length ? html`
            <div class="followups">
              ${this.message.suggestions.slice(0, uiConfig.maxSuggestions).map(s => html`
                <button class="followup" aria-label="Follow up: ${s}" @click=${() => this.handleFollowup(s)}>
                  <svg class="followup-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                    <path d="M5 12h14M12 5l7 7-7 7"/>
                  </svg>
                  ${s}
                </button>
              `)}
            </div>
          ` : ''}
        </div>
      </div>
    `;
  }
}
