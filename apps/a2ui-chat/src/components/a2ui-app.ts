import { LitElement, html, css } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import type { A2UIResponse } from '@a2ui/core';
import { ChatService, type ChatMessage, type LLMProvider } from '../services/chat-service';
import { authService, type AuthUser } from '../services/auth-service';
import { chatHistoryService, ChatHistoryService, type ChatThread } from '../services/chat-history-service';
import { uiConfig } from '../config/ui-config';
import { initTheme, toggleTheme, getTheme, type Theme } from '../services/theme-service';

@customElement('a2ui-app')
export class A2UIApp extends LitElement {
  static styles = css`
    :host {
      display: flex;
      flex-direction: column;
      height: 100vh;
      background: var(--a2ui-bg-app);
    }

    /* ── Header ──────────────────────────────────────────── */

    .header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      height: var(--a2ui-header-height);
      padding: 0 var(--a2ui-space-6);
      background: var(--a2ui-bg-primary);
      border-bottom: 1px solid var(--a2ui-border-subtle);
    }

    .header-left {
      display: flex;
      align-items: center;
      gap: var(--a2ui-space-4);
    }

    .header-right {
      display: flex;
      align-items: center;
      gap: var(--a2ui-space-3);
    }

    .logo {
      display: flex;
      align-items: center;
      gap: var(--a2ui-space-2);
      font-size: var(--a2ui-text-xl);
      font-weight: var(--a2ui-font-medium);
      color: var(--a2ui-text-primary);
    }

    .logo-icon {
      width: 32px;
      height: 32px;
      background: linear-gradient(135deg, #4285f4, #ea4335, #fbbc05, #34a853);
      border-radius: var(--a2ui-radius-md);
    }

    .divider {
      width: 1px;
      height: 24px;
      background: var(--a2ui-border-default);
    }

    .main {
      flex: 1;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }

    .header-btn {
      display: flex;
      align-items: center;
      gap: var(--a2ui-space-1);
      padding: var(--a2ui-space-2) var(--a2ui-space-3);
      background: transparent;
      border: 1px solid var(--a2ui-border-default);
      border-radius: var(--a2ui-radius-md);
      color: var(--a2ui-text-secondary);
      font-family: var(--a2ui-font-family);
      font-size: var(--a2ui-text-sm);
      cursor: pointer;
      transition: background-color var(--a2ui-transition-fast), color var(--a2ui-transition-fast), border-color var(--a2ui-transition-fast);
    }

    .header-btn:hover {
      background: var(--a2ui-bg-hover);
      color: var(--a2ui-text-primary);
      border-color: var(--a2ui-accent);
    }

    .header-btn.icon-btn {
      padding: var(--a2ui-space-2);
    }

    /* ── User info ───────────────────────────────────────── */

    .user-info {
      display: flex;
      align-items: center;
      gap: var(--a2ui-space-2);
      font-size: var(--a2ui-text-sm);
      color: var(--a2ui-text-secondary);
    }

    .user-avatar {
      width: 28px;
      height: 28px;
      border-radius: var(--a2ui-radius-full);
      background: var(--a2ui-accent);
      color: var(--a2ui-text-inverse);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 11px;
      font-weight: var(--a2ui-font-medium);
      overflow: hidden;
    }

    .user-avatar img {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }

    /* ── Auth loading / welcome ───────────────────────────── */

    .auth-loading {
      flex: 1;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .auth-loading .spinner {
      width: 24px;
      height: 24px;
      border: 2.5px solid var(--a2ui-border-default);
      border-top-color: var(--a2ui-accent);
      border-radius: 50%;
      animation: spin 0.7s linear infinite;
    }

    @keyframes spin {
      to { transform: rotate(360deg); }
    }

    .welcome-page {
      flex: 1;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      text-align: center;
      gap: var(--a2ui-space-6);
      padding: var(--a2ui-space-8);
    }

    .welcome-logo {
      width: 56px;
      height: 56px;
      background: linear-gradient(135deg, #4285f4, #ea4335, #fbbc05, #34a853);
      border-radius: var(--a2ui-radius-lg);
    }

    .welcome-page h1 {
      font-size: var(--a2ui-text-3xl);
      font-weight: var(--a2ui-font-medium);
      color: var(--a2ui-text-primary);
      margin: 0;
    }

    .welcome-page p {
      font-size: var(--a2ui-text-lg);
      color: var(--a2ui-text-secondary);
      max-width: 420px;
      margin: 0;
    }

    .get-started-btn {
      padding: var(--a2ui-space-3) var(--a2ui-space-8);
      background: var(--a2ui-accent);
      color: var(--a2ui-text-inverse);
      border: none;
      border-radius: var(--a2ui-radius-md);
      font-size: var(--a2ui-text-lg);
      font-weight: var(--a2ui-font-medium);
      font-family: var(--a2ui-font-family);
      cursor: pointer;
      transition: background-color 0.15s ease, transform 0.15s ease, box-shadow 0.15s ease;
    }

    .get-started-btn:hover {
      background: var(--a2ui-accent-hover);
      transform: translateY(-1px);
      box-shadow: 0 4px 16px rgba(138, 180, 248, 0.3);
    }
  `;

  // ── Chat state ──────────────────────────────────────────
  @state() private messages: ChatMessage[] = [];
  @state() private isLoading = false;
  @state() private providers: LLMProvider[] = [];
  @state() private selectedProvider = '';
  @state() private selectedModel = '';
  private activeThreadId: string | null = null;

  // ── Suggestions (data can come from AI, config, or any source) ──
  private suggestions = [
    'Compare iPhone vs Android',
    'Top 5 trending stocks',
    'Show weather forecast',
    'Explain machine learning',
    'Create a task list',
  ];

  // ── Auth state ──────────────────────────────────────────
  @state() private authLoading = true;
  @state() private isAuthenticated = false;
  @state() private user: AuthUser | null = null;
  @state() private showLogin = false;

  // ── Theme ───────────────────────────────────────────────
  @state() private theme: Theme = 'dark';

  private chatService = new ChatService();

  // ── History / back-button navigation ────────────────────
  // Two pushState calls: login modal open + first chat message.
  // Back pops them naturally. No hashes, no trapping, no redirects.
  private boundPopstate = this.onPopstate.bind(this);

  async connectedCallback() {
    super.connectedCallback();
    initTheme();
    this.theme = getTheme();
    window.addEventListener('popstate', this.boundPopstate);

    authService.addEventListener('change', () => {
      this.authLoading = authService.isLoading;
      this.isAuthenticated = authService.isAuthenticated;
      this.user = authService.user;

      if (this.isAuthenticated) {
        this.showLogin = false;
        // Pop the login modal entry so it doesn't linger in the stack
        if (history.state?.a2ui === 'login') {
          history.back();
        }
        // Scope localStorage to this user
        chatHistoryService.setUser(this.user?.sub ?? null);
        this.restoreLastThread();
        this.loadProviders();
      }
    });

    await authService.init();
    if (authService.isAuthenticated) {
      chatHistoryService.setUser(authService.user?.sub ?? null);
      this.restoreLastThread();
      await this.loadProviders();
    }
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    window.removeEventListener('popstate', this.boundPopstate);
  }

  // Saved conversation for forward-button restore
  private savedMessages: ChatMessage[] = [];

  private onPopstate() {
    const state = history.state;

    if (!this.isAuthenticated) {
      this.showLogin = state?.a2ui === 'login';
    } else if (state?.a2ui === 'chat' && this.messages.length === 0 && this.savedMessages.length > 0) {
      // Forward to active conversation → restore
      this.activeThreadId = state.threadId ?? this.activeThreadId;
      this.messages = this.savedMessages;
    } else if (state?.a2ui !== 'chat' && this.messages.length > 0) {
      // Back from active conversation → save and clear
      this.persistThread();
      this.savedMessages = [...this.messages];
      this.messages = [];
      this.activeThreadId = null;
    }
  }

  private openLogin() {
    this.showLogin = true;
    history.pushState({ a2ui: 'login' }, '');
  }

  private closeLogin() {
    this.showLogin = false;
    if (history.state?.a2ui === 'login') {
      history.back();
    }
  }

  private async loadProviders() {
    this.providers = await this.chatService.getProviders();
    if (this.providers.length > 0) {
      this.selectedProvider = this.providers[0].id;
      this.selectedModel = this.providers[0].models[0]?.id || '';
    }
  }

  private handleModelChange(e: CustomEvent<{ provider: string; model: string }>) {
    this.selectedProvider = e.detail.provider;
    this.selectedModel = e.detail.model;
  }

  // ── Persistence helpers ──────────────────────────────────

  private static readonly ACTIVE_KEY = 'a2ui_active_thread';

  /** Save the current thread to localStorage. */
  private persistThread() {
    if (!uiConfig.persistChat || !this.activeThreadId || this.messages.length === 0) return;

    const existing = chatHistoryService.getThread(this.activeThreadId);
    const thread: ChatThread = {
      id: this.activeThreadId,
      title: existing?.title ?? ChatHistoryService.titleFrom(this.messages[0].content),
      messages: this.messages,
      createdAt: existing?.createdAt ?? this.messages[0].timestamp,
      updatedAt: Date.now(),
      provider: this.selectedProvider || undefined,
      model: this.selectedModel || undefined,
    };
    chatHistoryService.saveThread(thread);
    sessionStorage.setItem(A2UIApp.ACTIVE_KEY, this.activeThreadId);
  }

  /** Restore the active thread on page refresh. */
  private restoreLastThread() {
    if (!uiConfig.persistChat) return;

    const activeId = sessionStorage.getItem(A2UIApp.ACTIVE_KEY);
    if (!activeId) return;

    const thread = chatHistoryService.getThread(activeId);
    if (thread) {
      this.activeThreadId = thread.id;
      this.messages = thread.messages;
    }
  }

  // ── Chat actions ───────────────────────────────────────

  private async handleSendMessage(e: CustomEvent<{ message: string }>) {
    const { message } = e.detail;
    if (!message.trim()) return;

    const isFirstMessage = this.messages.length === 0;

    // Start a new thread on first message
    if (isFirstMessage) {
      this.activeThreadId = crypto.randomUUID();
    }

    this.messages = [...this.messages, {
      id: crypto.randomUUID(),
      role: 'user',
      content: message,
      timestamp: Date.now(),
      avatarUrl: this.user?.picture || undefined,
      avatarInitials: this.getInitials(this.user!),
    }];

    // Push history entry on first message so back clears the conversation
    if (isFirstMessage) {
      history.pushState({ a2ui: 'chat', threadId: this.activeThreadId }, '');
    }

    this.persistThread();
    this.isLoading = true;

    try {
      const response = await this.chatService.sendMessage(
        message,
        this.selectedProvider,
        this.selectedModel,
        this.messages
      );

      const provider = this.providers.find(p => p.id === this.selectedProvider);
      const model = provider?.models.find(m => m.id === this.selectedModel);

      this.messages = [...this.messages, {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: response.text || '',
        a2ui: response.a2ui,
        timestamp: Date.now(),
        model: model?.name || this.selectedModel,
        suggestions: response.suggestions,
      }];

      this.persistThread();
    } catch (error) {
      console.error('Chat error:', error);
      this.messages = [...this.messages, {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: 'Sorry, there was an error processing your request.',
        timestamp: Date.now(),
      }];
      this.persistThread();
    } finally {
      this.isLoading = false;
    }
  }

  private clearChat() {
    // Persist before clearing so the thread stays in history
    this.persistThread();
    this.messages = [];
    this.activeThreadId = null;
    this.savedMessages = [];
    sessionStorage.removeItem(A2UIApp.ACTIVE_KEY);
    if (history.state?.a2ui === 'chat') {
      history.back();
    }
  }

  private handleToggleTheme() {
    this.theme = toggleTheme();
  }

  private async handleLogout() {
    await authService.logout();
  }

  private getInitials(user: AuthUser): string {
    if (user.name) return user.name.charAt(0).toUpperCase();
    if (user.email) return user.email.charAt(0).toUpperCase();
    return 'U';
  }

  // ── Render ──────────────────────────────────────────────

  render() {
    // Auth loading
    if (this.authLoading) {
      return html`
        <div class="auth-loading">
          <div class="spinner"></div>
        </div>
      `;
    }

    // Not authenticated — welcome + login
    if (!this.isAuthenticated) {
      return html`
        <div class="welcome-page">
          <div class="welcome-logo"></div>
          <h1>Welcome to A2UI Chat</h1>
          <p>AI-powered assistant with rich interactive responses. Sign in to get started.</p>
          <button class="get-started-btn" @click=${this.openLogin}>
            Get Started
          </button>
        </div>
        ${this.showLogin ? html`
          <a2ui-login @close=${this.closeLogin}></a2ui-login>
        ` : ''}
      `;
    }

    // Authenticated — full chat UI
    return html`
      <header class="header">
        <div class="header-left">
          <div class="logo">
            <div class="logo-icon"></div>
            <span>A2UI Chat</span>
          </div>
          <div class="divider"></div>
          <a2ui-model-selector
            .providers=${this.providers}
            .selectedProvider=${this.selectedProvider}
            .selectedModel=${this.selectedModel}
            @model-change=${this.handleModelChange}
          ></a2ui-model-selector>
        </div>

        <div class="header-right">
          ${this.user ? html`
            <div class="user-info">
              <div class="user-avatar">
                ${this.user.picture
                  ? html`<img src=${this.user.picture} alt="" />`
                  : this.getInitials(this.user)}
              </div>
              <!--<span>${this.user.email}</span>-->
            </div>
          ` : ''}

          ${this.messages.length > 0 ? html`
            <button class="header-btn" @click=${this.clearChat}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
              </svg>
              Clear
            </button>
          ` : ''}

          <button class="header-btn icon-btn" @click=${this.handleToggleTheme} title="${this.theme === 'dark' ? 'Light mode' : 'Dark mode'}">
            ${this.theme === 'dark' ? html`
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 7c-2.76 0-5 2.24-5 5s2.24 5 5 5 5-2.24 5-5-2.24-5-5-5zM2 13h2c.55 0 1-.45 1-1s-.45-1-1-1H2c-.55 0-1 .45-1 1s.45 1 1 1zm18 0h2c.55 0 1-.45 1-1s-.45-1-1-1h-2c-.55 0-1 .45-1 1s.45 1 1 1zM11 2v2c0 .55.45 1 1 1s1-.45 1-1V2c0-.55-.45-1-1-1s-1 .45-1 1zm0 18v2c0 .55.45 1 1 1s1-.45 1-1v-2c0-.55-.45-1-1-1s-1 .45-1 1zM5.99 4.58a.996.996 0 00-1.41 0 .996.996 0 000 1.41l1.06 1.06c.39.39 1.03.39 1.41 0s.39-1.03 0-1.41L5.99 4.58zm12.37 12.37a.996.996 0 00-1.41 0 .996.996 0 000 1.41l1.06 1.06c.39.39 1.03.39 1.41 0a.996.996 0 000-1.41l-1.06-1.06zm1.06-10.96a.996.996 0 000-1.41.996.996 0 00-1.41 0l-1.06 1.06c-.39.39-.39 1.03 0 1.41s1.03.39 1.41 0l1.06-1.06zM7.05 18.36a.996.996 0 000-1.41.996.996 0 00-1.41 0l-1.06 1.06c-.39.39-.39 1.03 0 1.41s1.03.39 1.41 0l1.06-1.06z"/>
              </svg>
            ` : html`
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 3a9 9 0 109 9c0-.46-.04-.92-.1-1.36a5.389 5.389 0 01-4.4 2.26 5.403 5.403 0 01-3.14-9.8c-.44-.06-.9-.1-1.36-.1z"/>
              </svg>
            `}
          </button>

          <button class="header-btn" @click=${this.handleLogout}>
            Logout
          </button>
        </div>
      </header>

      <main class="main">
        <a2ui-chat-container
          .messages=${this.messages}
          .isLoading=${this.isLoading}
          .suggestions=${this.suggestions}
          @send-message=${this.handleSendMessage}
        ></a2ui-chat-container>
      </main>
    `;
  }
}
