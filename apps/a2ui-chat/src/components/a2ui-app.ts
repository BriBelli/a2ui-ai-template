import { LitElement, html, css } from "lit";
import { customElement, state } from "lit/decorators.js";
import type { A2UIResponse } from "@a2ui/core";
import {
  ChatService,
  type ChatMessage,
  type LLMProvider,
} from "../services/chat-service";
import { authService, type AuthUser } from "../services/auth-service";
import {
  chatHistoryService,
  ChatHistoryService,
  type ChatThread,
} from "../services/chat-history-service";
import { uiConfig } from "../config/ui-config";
import {
  initTheme,
  toggleTheme,
  getTheme,
  type Theme,
} from "../services/theme-service";
import { isLocationCached } from "../services/geolocation-service";
import type { ThinkingStep } from "./chat/a2ui-thinking-indicator";

@customElement("a2ui-app")
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
      transition:
        background-color var(--a2ui-transition-fast),
        color var(--a2ui-transition-fast),
        border-color var(--a2ui-transition-fast);
    }

    .header-btn:hover {
      background: var(--a2ui-bg-hover);
      color: var(--a2ui-text-primary);
      border-color: var(--a2ui-accent);
    }

    .header-btn.icon-btn {
      padding: var(--a2ui-space-2);
    }

    /* ── Avatar & popover ────────────────────────────────── */

    .avatar-wrapper {
      position: relative;
    }

    .avatar-btn {
      width: 32px;
      height: 32px;
      border-radius: var(--a2ui-radius-full);
      background: var(--a2ui-accent);
      color: var(--a2ui-text-inverse);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 12px;
      font-weight: var(--a2ui-font-medium);
      overflow: hidden;
      border: 2px solid transparent;
      cursor: pointer;
      padding: 0;
      transition:
        border-color 0.15s ease,
        box-shadow 0.15s ease;
    }

    .avatar-btn:hover,
    .avatar-btn.active {
      border-color: var(--a2ui-accent);
      box-shadow: 0 0 0 2px var(--a2ui-accent-subtle);
    }

    .avatar-btn img {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }

    /* ── User menu popover ────────────────────────────────── */

    .user-menu-backdrop {
      position: fixed;
      inset: 0;
      z-index: 99;
    }

    .user-menu {
      position: absolute;
      top: calc(100% + 8px);
      right: 0;
      width: 240px;
      background: var(--a2ui-bg-secondary);
      border: 1px solid var(--a2ui-border-default);
      border-radius: var(--a2ui-radius-lg);
      box-shadow: var(--a2ui-shadow-lg);
      z-index: 100;
      overflow: hidden;
      transform-origin: top right;
      animation: menuIn 0.15s cubic-bezier(0.22, 1, 0.36, 1);
    }

    @keyframes menuIn {
      from {
        opacity: 0;
        transform: scale(0.95) translateY(-4px);
      }
      to {
        opacity: 1;
        transform: scale(1) translateY(0);
      }
    }

    .user-menu-header {
      padding: var(--a2ui-space-4);
      border-bottom: 1px solid var(--a2ui-border-subtle);
      display: flex;
      align-items: center;
      gap: var(--a2ui-space-3);
    }

    .user-menu-avatar {
      width: 36px;
      height: 36px;
      border-radius: var(--a2ui-radius-full);
      background: var(--a2ui-accent);
      color: var(--a2ui-text-inverse);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 14px;
      font-weight: var(--a2ui-font-medium);
      overflow: hidden;
      flex-shrink: 0;
    }

    .user-menu-avatar img {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }

    .user-menu-info {
      min-width: 0;
    }

    .user-menu-name {
      font-size: var(--a2ui-text-sm);
      font-weight: var(--a2ui-font-medium);
      color: var(--a2ui-text-primary);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .user-menu-email {
      font-size: var(--a2ui-text-xs);
      color: var(--a2ui-text-tertiary);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .user-menu-body {
      padding: var(--a2ui-space-2) 0;
    }

    .menu-item {
      display: flex;
      align-items: center;
      gap: var(--a2ui-space-3);
      width: 100%;
      padding: var(--a2ui-space-2) var(--a2ui-space-4);
      background: none;
      border: none;
      font-family: var(--a2ui-font-family);
      font-size: var(--a2ui-text-sm);
      color: var(--a2ui-text-primary);
      cursor: pointer;
      transition: background-color 0.1s ease;
      text-align: left;
    }

    .menu-item:hover {
      background: var(--a2ui-bg-hover);
    }

    .menu-item svg {
      width: 16px;
      height: 16px;
      color: var(--a2ui-text-secondary);
      flex-shrink: 0;
    }

    .menu-item .theme-label {
      flex: 1;
    }

    .menu-divider {
      height: 1px;
      background: var(--a2ui-border-subtle);
      margin: var(--a2ui-space-1) 0;
    }

    .menu-item.danger {
      color: var(--a2ui-error);
    }

    .menu-item.danger svg {
      color: var(--a2ui-error);
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
      to {
        transform: rotate(360deg);
      }
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
      transition:
        background-color 0.15s ease,
        transform 0.15s ease,
        box-shadow 0.15s ease;
    }

    .get-started-btn:hover {
      background: var(--a2ui-accent-hover);
      transform: translateY(-1px);
      box-shadow: 0 4px 16px rgba(138, 180, 248, 0.3);
    }

    /* ── Responsive: Tablet (≤768px) ──────────────────── */

    @media (max-width: 768px) {
      .header {
        height: 56px;
        padding: 0 var(--a2ui-space-4);
      }

      .logo {
        font-size: var(--a2ui-text-lg);
      }

      .logo-icon {
        width: 28px;
        height: 28px;
      }

      .divider {
        height: 20px;
      }

      .welcome-page {
        padding: var(--a2ui-space-6);
      }

      .welcome-page h1 {
        font-size: var(--a2ui-text-2xl);
      }

      .welcome-page p {
        font-size: var(--a2ui-text-md);
      }
    }

    /* ── Responsive: Mobile (≤480px) ─────────────────── */

    @media (max-width: 480px) {
      .header {
        height: auto;
        flex-wrap: wrap;
        padding: var(--a2ui-space-2) var(--a2ui-space-3);
        gap: var(--a2ui-space-2);
      }

      .header-left {
        flex: 1;
        min-width: 0;
        gap: var(--a2ui-space-2);
      }

      .header-right {
        flex-shrink: 0;
      }

      .logo {
        font-size: var(--a2ui-text-md);
        gap: var(--a2ui-space-1);
      }

      .logo span {
        display: none;
      }

      .logo-icon {
        width: 28px;
        height: 28px;
      }

      .divider {
        display: none;
      }

      .header-btn {
        padding: var(--a2ui-space-1) var(--a2ui-space-2);
        font-size: var(--a2ui-text-xs);
      }

      .avatar-btn {
        width: 28px;
        height: 28px;
        font-size: 11px;
      }

      .user-menu {
        width: calc(100vw - var(--a2ui-space-6));
        right: calc(-1 * var(--a2ui-space-3));
      }

      .welcome-page {
        padding: var(--a2ui-space-4);
        gap: var(--a2ui-space-4);
      }

      .welcome-logo {
        width: 44px;
        height: 44px;
      }

      .welcome-page h1 {
        font-size: var(--a2ui-text-xl);
      }

      .welcome-page p {
        font-size: var(--a2ui-text-sm);
      }

      .get-started-btn {
        padding: var(--a2ui-space-3) var(--a2ui-space-6);
        font-size: var(--a2ui-text-md);
      }
    }
  `;

  // ── Chat state ──────────────────────────────────────────
  @state() private messages: ChatMessage[] = [];
  @state() private isLoading = false;
  @state() private providers: LLMProvider[] = [];
  @state() private selectedProvider = "";
  @state() private selectedModel = "";
  @state() private activeThreadId: string | null = null;
  @state() private threads: ChatThread[] = [];

  // ── Suggestions (data can come from AI, config, or any source) ──
  private suggestions = [
    "Compare iPhone vs Android",
    "Top 5 trending stocks",
    "Show weather forecast",
    "Explain machine learning",
    "Create a task list",
  ];

  // ── Auth state ──────────────────────────────────────────
  @state() private authLoading = true;
  @state() private isAuthenticated = false;
  @state() private user: AuthUser | null = null;
  @state() private showLogin = false;

  // ── Theme ───────────────────────────────────────────────
  @state() private theme: Theme = "dark";

  // ── User menu ──────────────────────────────────────────
  @state() private showUserMenu = false;

  // ── Thinking steps (drives the loading indicator) ──────
  @state() private thinkingSteps: ThinkingStep[] = [];

  private chatService = new ChatService();

  // ── History / back-button navigation ────────────────────
  // Two pushState calls: login modal open + first chat message.
  // Back pops them naturally. No hashes, no trapping, no redirects.
  private boundPopstate = this.onPopstate.bind(this);

  async connectedCallback() {
    super.connectedCallback();
    initTheme();
    this.theme = getTheme();
    window.addEventListener("popstate", this.boundPopstate);

    authService.addEventListener("change", () => {
      this.authLoading = authService.isLoading;
      this.isAuthenticated = authService.isAuthenticated;
      this.user = authService.user;

      if (this.isAuthenticated) {
        this.showLogin = false;
        // Pop the login modal entry so it doesn't linger in the stack
        if (history.state?.a2ui === "login") {
          history.back();
        }
        // Scope localStorage to this user
        chatHistoryService.setUser(this.user?.sub ?? null);
        this.restoreLastThread();
        this.refreshThreadList();
        this.loadProviders();
      }
    });

    await authService.init();
    if (authService.isAuthenticated) {
      chatHistoryService.setUser(authService.user?.sub ?? null);
      this.restoreLastThread();
      this.refreshThreadList();
      await this.loadProviders();
    }
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    window.removeEventListener("popstate", this.boundPopstate);
  }

  // Saved conversation for forward-button restore
  private savedMessages: ChatMessage[] = [];

  private onPopstate() {
    const state = history.state;

    if (!this.isAuthenticated) {
      this.showLogin = state?.a2ui === "login";
    } else if (
      state?.a2ui === "chat" &&
      this.messages.length === 0 &&
      this.savedMessages.length > 0
    ) {
      // Forward to active conversation → restore
      this.activeThreadId = state.threadId ?? this.activeThreadId;
      this.messages = this.savedMessages;
    } else if (state?.a2ui !== "chat" && this.messages.length > 0) {
      // Back from active conversation → save and clear
      this.persistThread();
      this.savedMessages = [...this.messages];
      this.messages = [];
      this.activeThreadId = null;
    }
    this.refreshThreadList();
  }

  private openLogin() {
    this.showLogin = true;
    history.pushState({ a2ui: "login" }, "");
  }

  private closeLogin() {
    this.showLogin = false;
    if (history.state?.a2ui === "login") {
      history.back();
    }
  }

  private async loadProviders() {
    this.providers = await this.chatService.getProviders();
    if (this.providers.length > 0) {
      this.selectedProvider = this.providers[0].id;
      this.selectedModel = this.providers[0].models[0]?.id || "";
    }
  }

  private handleModelChange(
    e: CustomEvent<{ provider: string; model: string }>,
  ) {
    this.selectedProvider = e.detail.provider;
    this.selectedModel = e.detail.model;
  }

  // ── Persistence helpers ──────────────────────────────────

  private static readonly ACTIVE_KEY = "a2ui_active_thread";

  /** Save the current thread to localStorage. */
  private persistThread() {
    if (
      !uiConfig.persistChat ||
      !this.activeThreadId ||
      this.messages.length === 0
    )
      return;

    const existing = chatHistoryService.getThread(this.activeThreadId);
    const thread: ChatThread = {
      id: this.activeThreadId,
      title:
        existing?.title ??
        ChatHistoryService.titleFrom(this.messages[0].content),
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

    this.messages = [
      ...this.messages,
      {
        id: crypto.randomUUID(),
        role: "user",
        content: message,
        timestamp: Date.now(),
        avatarUrl: this.user?.picture || undefined,
        avatarInitials: this.getInitials(this.user!),
      },
    ];

    // Push history entry on first message so back clears the conversation
    if (isFirstMessage) {
      history.pushState({ a2ui: "chat", threadId: this.activeThreadId }, "");
    }

    this.persistThread();
    this.refreshThreadList();
    this.isLoading = true;

    // Build dynamic steps array that reflects real operations
    const steps: ThinkingStep[] = [];
    const willSearch = this.chatService.willSearch(message);
    const needsLocation = this.chatService.needsLocation(message);
    const locationCached = isLocationCached();

    // Helper to update the reactive property
    const push = (label: string, detail?: string) => {
      steps.push({ label, done: false, detail });
      this.thinkingSteps = [...steps];
    };
    const done = (index: number) => {
      steps[index] = { ...steps[index], done: true };
      this.thinkingSteps = [...steps];
    };

    try {
      const response = await this.chatService.sendMessage(
        message,
        this.selectedProvider,
        this.selectedModel,
        this.messages,
        // Progress callback — driven by real lifecycle events
        (phase, detail) => {
          switch (phase) {
            case "location":
              if (needsLocation && !locationCached) {
                push("Getting your location");
              }
              break;
            case "location-done": {
              const locIdx = steps.findIndex((s) =>
                s.label.startsWith("Getting"),
              );
              if (locIdx >= 0) done(locIdx);
              break;
            }
            case "searching":
              push("Searching the web");
              break;
            case "search-done": {
              const searchIdx = steps.findIndex((s) =>
                s.label.startsWith("Searching"),
              );
              if (searchIdx >= 0) {
                // Update the step with the rewritten query from the backend
                if (detail) {
                  steps[searchIdx] = {
                    ...steps[searchIdx],
                    detail: `"${detail}"`,
                  };
                }
                done(searchIdx);
              }
              break;
            }
            case "generating":
              push("Generating response");
              break;
          }
        },
      );

      // Mark all steps done
      steps.forEach((_, i) => done(i));

      const provider = this.providers.find(
        (p) => p.id === this.selectedProvider,
      );
      const model = provider?.models.find((m) => m.id === this.selectedModel);

      this.messages = [
        ...this.messages,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: response.text || "",
          a2ui: response.a2ui,
          timestamp: Date.now(),
          model: model?.name || this.selectedModel,
          suggestions: response.suggestions,
        },
      ];

      this.persistThread();
      this.refreshThreadList();
    } catch (error) {
      console.error("Chat error:", error);
      this.messages = [
        ...this.messages,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: "Sorry, there was an error processing your request.",
          timestamp: Date.now(),
        },
      ];
      this.persistThread();
      this.refreshThreadList();
    } finally {
      this.isLoading = false;
      this.thinkingSteps = [];
    }
  }

  private newChat() {
    // Persist current thread before starting fresh
    this.persistThread();
    this.messages = [];
    this.activeThreadId = null;
    this.savedMessages = [];
    sessionStorage.removeItem(A2UIApp.ACTIVE_KEY);
    this.refreshThreadList();
    if (history.state?.a2ui === "chat") {
      history.back();
    }
  }

  private switchThread(e: CustomEvent<{ threadId: string }>) {
    const { threadId } = e.detail;
    if (threadId === this.activeThreadId) return;

    // Save current thread first
    this.persistThread();

    // Load requested thread
    const thread = chatHistoryService.getThread(threadId);
    if (thread) {
      this.activeThreadId = thread.id;
      this.messages = thread.messages;
      sessionStorage.setItem(A2UIApp.ACTIVE_KEY, thread.id);

      // Restore provider/model if saved
      if (thread.provider) this.selectedProvider = thread.provider;
      if (thread.model) this.selectedModel = thread.model;

      if (history.state?.a2ui !== "chat") {
        history.pushState({ a2ui: "chat", threadId: thread.id }, "");
      }
    }
    this.refreshThreadList();
  }

  private deleteThread(e: CustomEvent<{ threadId: string }>) {
    const { threadId } = e.detail;
    chatHistoryService.deleteThread(threadId);

    if (threadId === this.activeThreadId) {
      // Deleted the active thread — clear UI
      this.messages = [];
      this.activeThreadId = null;
      this.savedMessages = [];
      sessionStorage.removeItem(A2UIApp.ACTIVE_KEY);
      if (history.state?.a2ui === "chat") {
        history.back();
      }
    }
    this.refreshThreadList();
  }

  private renameThread(e: CustomEvent<{ threadId: string; title: string }>) {
    const { threadId, title } = e.detail;
    const thread = chatHistoryService.getThread(threadId);
    if (thread) {
      thread.title = title;
      chatHistoryService.saveThread(thread);
    }
    this.refreshThreadList();
  }

  private refreshThreadList() {
    this.threads = chatHistoryService.getThreads();
  }

  private toggleUserMenu() {
    this.showUserMenu = !this.showUserMenu;
  }

  private closeUserMenu() {
    this.showUserMenu = false;
  }

  private handleToggleTheme() {
    this.theme = toggleTheme();
  }

  private async handleLogout() {
    this.showUserMenu = false;
    await authService.logout();
  }

  private getInitials(user: AuthUser): string {
    if (user.name) return user.name.charAt(0).toUpperCase();
    if (user.email) return user.email.charAt(0).toUpperCase();
    return "U";
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
          <p>
            AI-powered assistant with rich interactive responses. Sign in to get
            started.
          </p>
          <button class="get-started-btn" @click=${this.openLogin}>
            Get Started
          </button>
        </div>
        ${this.showLogin
          ? html` <a2ui-login @close=${this.closeLogin}></a2ui-login> `
          : ""}
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
          ${this.user
            ? html`
                <div class="avatar-wrapper">
                  <button
                    class="avatar-btn ${this.showUserMenu ? "active" : ""}"
                    @click=${this.toggleUserMenu}
                    title=${this.user.name || this.user.email || "Account"}
                  >
                    ${this.user.picture
                      ? html`<img src=${this.user.picture} alt="" />`
                      : this.getInitials(this.user)}
                  </button>

                  ${this.showUserMenu
                    ? html`
                        <div
                          class="user-menu-backdrop"
                          @click=${this.closeUserMenu}
                        ></div>
                        <div class="user-menu">
                          <div class="user-menu-header">
                            <div class="user-menu-avatar">
                              ${this.user.picture
                                ? html`<img src=${this.user.picture} alt="" />`
                                : this.getInitials(this.user)}
                            </div>
                            <div class="user-menu-info">
                              ${this.user.name
                                ? html`<div class="user-menu-name">
                                    ${this.user.name}
                                  </div>`
                                : ""}
                              ${this.user.email
                                ? html`<div class="user-menu-email">
                                    ${this.user.email}
                                  </div>`
                                : ""}
                            </div>
                          </div>

                          <div class="user-menu-body">
                            <!-- Theme toggle -->
                            <button
                              class="menu-item"
                              @click=${this.handleToggleTheme}
                            >
                              ${this.theme === "dark"
                                ? html`
                                    <svg
                                      viewBox="0 0 24 24"
                                      fill="currentColor"
                                    >
                                      <path
                                        d="M12 7c-2.76 0-5 2.24-5 5s2.24 5 5 5 5-2.24 5-5-2.24-5-5-5zM2 13h2c.55 0 1-.45 1-1s-.45-1-1-1H2c-.55 0-1 .45-1 1s.45 1 1 1zm18 0h2c.55 0 1-.45 1-1s-.45-1-1-1h-2c-.55 0-1 .45-1 1s.45 1 1 1zM11 2v2c0 .55.45 1 1 1s1-.45 1-1V2c0-.55-.45-1-1-1s-1 .45-1 1zm0 18v2c0 .55.45 1 1 1s1-.45 1-1v-2c0-.55-.45-1-1-1s-1 .45-1 1zM5.99 4.58a.996.996 0 00-1.41 0 .996.996 0 000 1.41l1.06 1.06c.39.39 1.03.39 1.41 0s.39-1.03 0-1.41L5.99 4.58zm12.37 12.37a.996.996 0 00-1.41 0 .996.996 0 000 1.41l1.06 1.06c.39.39 1.03.39 1.41 0a.996.996 0 000-1.41l-1.06-1.06zm1.06-10.96a.996.996 0 000-1.41.996.996 0 00-1.41 0l-1.06 1.06c-.39.39-.39 1.03 0 1.41s1.03.39 1.41 0l1.06-1.06zM7.05 18.36a.996.996 0 000-1.41.996.996 0 00-1.41 0l-1.06 1.06c-.39.39-.39 1.03 0 1.41s1.03.39 1.41 0l1.06-1.06z"
                                      />
                                    </svg>
                                    <span class="theme-label">Light mode</span>
                                  `
                                : html`
                                    <svg
                                      viewBox="0 0 24 24"
                                      fill="currentColor"
                                    >
                                      <path
                                        d="M12 3a9 9 0 109 9c0-.46-.04-.92-.1-1.36a5.389 5.389 0 01-4.4 2.26 5.403 5.403 0 01-3.14-9.8c-.44-.06-.9-.1-1.36-.1z"
                                      />
                                    </svg>
                                    <span class="theme-label">Dark mode</span>
                                  `}
                            </button>

                            <!-- Settings -->
                            <button
                              class="menu-item"
                              @click=${() => {
                                /* TODO: open settings */ this.closeUserMenu();
                              }}
                            >
                              <svg viewBox="0 0 24 24" fill="currentColor">
                                <path
                                  d="M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58a.49.49 0 00.12-.61l-1.92-3.32a.488.488 0 00-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54a.484.484 0 00-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.07.62-.07.94s.02.64.07.94l-2.03 1.58a.49.49 0 00-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6A3.6 3.6 0 1112 8.4a3.6 3.6 0 010 7.2z"
                                />
                              </svg>
                              <span>Settings</span>
                            </button>

                            <div class="menu-divider"></div>

                            <!-- Logout -->
                            <button
                              class="menu-item danger"
                              @click=${this.handleLogout}
                            >
                              <svg viewBox="0 0 24 24" fill="currentColor">
                                <path
                                  d="M17 7l-1.41 1.41L18.17 11H8v2h10.17l-2.58 2.58L17 17l5-5zM4 5h8V3H4c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h8v-2H4V5z"
                                />
                              </svg>
                              <span>Sign out</span>
                            </button>
                          </div>
                        </div>
                      `
                    : ""}
                </div>
              `
            : ""}
        </div>
      </header>

      <a2ui-thread-tabs
        .threads=${this.threads}
        .activeThreadId=${this.activeThreadId}
        @new-chat=${this.newChat}
        @switch-thread=${this.switchThread}
        @delete-thread=${this.deleteThread}
        @rename-thread=${this.renameThread}
      ></a2ui-thread-tabs>

      <main class="main">
        <a2ui-chat-container
          .messages=${this.messages}
          .isLoading=${this.isLoading}
          .suggestions=${this.suggestions}
          .thinkingSteps=${this.thinkingSteps}
          @send-message=${this.handleSendMessage}
        ></a2ui-chat-container>
      </main>

      <a2ui-toast></a2ui-toast>
    `;
  }
}
