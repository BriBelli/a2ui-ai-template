import { LitElement, html, css, nothing } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import {
  aiConfig,
  setAIConfig,
  type ContentStyle,
  type PerformanceMode,
} from '../config/ui-config';

interface StyleOption {
  id: string;
  name: string;
  description: string;
}

@customElement('a2ui-settings-panel')
export class A2UISettingsPanel extends LitElement {
  static styles = css`
    :host {
      display: block;
    }

    /* ── Backdrop ───────────────────────────────────────── */

    .backdrop {
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.4);
      z-index: 200;
      animation: fadeIn 0.2s ease;
    }

    @keyframes fadeIn {
      from { opacity: 0; }
      to { opacity: 1; }
    }

    /* ── Panel ─────────────────────────────────────────── */

    .panel {
      position: fixed;
      top: 0;
      right: 0;
      bottom: 0;
      width: 380px;
      max-width: 100vw;
      background: var(--a2ui-bg-primary);
      border-left: 1px solid var(--a2ui-border-subtle);
      box-shadow: var(--a2ui-shadow-xl);
      z-index: 201;
      display: flex;
      flex-direction: column;
      animation: slideIn 0.25s cubic-bezier(0.22, 1, 0.36, 1);
    }

    @keyframes slideIn {
      from { transform: translateX(100%); }
      to { transform: translateX(0); }
    }

    /* ── Header ────────────────────────────────────────── */

    .panel-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: var(--a2ui-space-5) var(--a2ui-space-6);
      border-bottom: 1px solid var(--a2ui-border-subtle);
      flex-shrink: 0;
    }

    .panel-title {
      font-size: var(--a2ui-text-lg);
      font-weight: var(--a2ui-font-semibold);
      color: var(--a2ui-text-primary);
      margin: 0;
    }

    .close-btn {
      width: 32px;
      height: 32px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: none;
      border: none;
      border-radius: var(--a2ui-radius-md);
      color: var(--a2ui-text-secondary);
      cursor: pointer;
      transition: background-color var(--a2ui-transition-fast),
                  color var(--a2ui-transition-fast);
    }

    .close-btn:hover {
      background: var(--a2ui-bg-hover);
      color: var(--a2ui-text-primary);
    }

    .close-btn svg {
      width: 18px;
      height: 18px;
    }

    /* ── Body ──────────────────────────────────────────── */

    .panel-body {
      flex: 1;
      overflow-y: auto;
      padding: var(--a2ui-space-6);
    }

    /* ── Section ───────────────────────────────────────── */

    .section {
      margin-bottom: var(--a2ui-space-8);
    }

    .section:last-child {
      margin-bottom: 0;
    }

    .section-label {
      font-size: 11px;
      font-weight: var(--a2ui-font-semibold);
      color: var(--a2ui-text-tertiary);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin: 0 0 var(--a2ui-space-4);
    }

    /* ── Field ─────────────────────────────────────────── */

    .field {
      margin-bottom: var(--a2ui-space-5);
    }

    .field:last-child {
      margin-bottom: 0;
    }

    .field-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: var(--a2ui-space-3);
    }

    .field-info {
      flex: 1;
      min-width: 0;
    }

    .field-label {
      font-size: var(--a2ui-text-sm);
      font-weight: var(--a2ui-font-medium);
      color: var(--a2ui-text-primary);
      margin: 0 0 2px;
    }

    .field-desc {
      font-size: var(--a2ui-text-xs);
      color: var(--a2ui-text-tertiary);
      margin: 0;
      line-height: 1.4;
    }

    /* ── Select ────────────────────────────────────────── */

    .field-select {
      appearance: none;
      background: var(--a2ui-bg-secondary);
      border: 1px solid var(--a2ui-border-default);
      border-radius: var(--a2ui-radius-md);
      padding: 6px 32px 6px 10px;
      font-family: var(--a2ui-font-family);
      font-size: var(--a2ui-text-sm);
      color: var(--a2ui-text-primary);
      cursor: pointer;
      min-width: 130px;
      transition: border-color var(--a2ui-transition-fast),
                  box-shadow var(--a2ui-transition-fast);
      background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='%239aa0a6'%3E%3Cpath d='M7 10l5 5 5-5z'/%3E%3C/svg%3E");
      background-repeat: no-repeat;
      background-position: right 8px center;
    }

    .field-select:hover {
      border-color: var(--a2ui-accent);
    }

    .field-select:focus {
      outline: none;
      border-color: var(--a2ui-accent);
      box-shadow: 0 0 0 2px var(--a2ui-accent-subtle);
    }

    /* ── Toggle switch ─────────────────────────────────── */

    .toggle {
      position: relative;
      width: 40px;
      height: 22px;
      flex-shrink: 0;
    }

    .toggle input {
      opacity: 0;
      width: 0;
      height: 0;
      position: absolute;
    }

    .toggle-track {
      position: absolute;
      inset: 0;
      background: var(--a2ui-bg-tertiary);
      border: 1px solid var(--a2ui-border-default);
      border-radius: 11px;
      cursor: pointer;
      transition: background-color 0.2s ease, border-color 0.2s ease;
    }

    .toggle-track::after {
      content: '';
      position: absolute;
      top: 2px;
      left: 2px;
      width: 16px;
      height: 16px;
      background: var(--a2ui-text-secondary);
      border-radius: 50%;
      transition: transform 0.2s ease, background-color 0.2s ease;
    }

    .toggle input:checked + .toggle-track {
      background: var(--a2ui-accent);
      border-color: var(--a2ui-accent);
    }

    .toggle input:checked + .toggle-track::after {
      transform: translateX(18px);
      background: #fff;
    }

    .toggle input:focus-visible + .toggle-track {
      box-shadow: 0 0 0 2px var(--a2ui-accent-subtle);
    }

    /* ── Number input ──────────────────────────────────── */

    .field-number {
      width: 64px;
      text-align: center;
      appearance: none;
      -moz-appearance: textfield;
      background: var(--a2ui-bg-secondary);
      border: 1px solid var(--a2ui-border-default);
      border-radius: var(--a2ui-radius-md);
      padding: 6px 8px;
      font-family: var(--a2ui-font-family);
      font-size: var(--a2ui-text-sm);
      color: var(--a2ui-text-primary);
      transition: border-color var(--a2ui-transition-fast),
                  box-shadow var(--a2ui-transition-fast);
    }

    .field-number::-webkit-inner-spin-button,
    .field-number::-webkit-outer-spin-button {
      -webkit-appearance: none;
      margin: 0;
    }

    .field-number:focus {
      outline: none;
      border-color: var(--a2ui-accent);
      box-shadow: 0 0 0 2px var(--a2ui-accent-subtle);
    }

    /* ── Divider ───────────────────────────────────────── */

    .divider {
      height: 1px;
      background: var(--a2ui-border-subtle);
      margin: var(--a2ui-space-6) 0;
    }

    /* ── Responsive ────────────────────────────────────── */

    @media (max-width: 480px) {
      .panel {
        width: 100vw;
      }

      .panel-body {
        padding: var(--a2ui-space-4);
      }

      .field-select {
        min-width: 110px;
      }
    }
  `;

  @property({ type: Boolean }) open = false;

  @state() private contentStyle: ContentStyle = aiConfig.contentStyle;
  @state() private performanceMode: PerformanceMode = aiConfig.performanceMode;
  @state() private webSearch = aiConfig.webSearch;
  @state() private conversationHistory = aiConfig.conversationHistory;
  @state() private maxHistoryMessages = aiConfig.maxHistoryMessages;
  @state() private styles: StyleOption[] = [];

  private static _cachedStyles: StyleOption[] | null = null;

  connectedCallback() {
    super.connectedCallback();
    this.syncFromConfig();
    if (A2UISettingsPanel._cachedStyles) {
      this.styles = A2UISettingsPanel._cachedStyles;
    } else {
      this.fetchStyles();
    }
  }

  private syncFromConfig() {
    this.contentStyle = aiConfig.contentStyle;
    this.performanceMode = aiConfig.performanceMode;
    this.webSearch = aiConfig.webSearch;
    this.conversationHistory = aiConfig.conversationHistory;
    this.maxHistoryMessages = aiConfig.maxHistoryMessages;
  }

  private async fetchStyles() {
    try {
      const resp = await fetch('/api/styles');
      if (resp.ok) {
        const data = await resp.json();
        this.styles = data.styles ?? [];
        A2UISettingsPanel._cachedStyles = this.styles;
      }
    } catch {
      this.styles = [
        { id: 'analytical', name: 'Analytical', description: 'Data dashboards' },
        { id: 'content', name: 'Content', description: 'Narrative & editorial' },
        { id: 'comparison', name: 'Comparison', description: 'Side-by-side analysis' },
        { id: 'howto', name: 'How-To', description: 'Step-by-step guides' },
        { id: 'quick', name: 'Quick Answer', description: 'Concise responses' },
      ];
    }
  }

  updated(changed: Map<string, unknown>) {
    if (changed.has('open') && this.open) {
      this.syncFromConfig();
    }
  }

  private close() {
    this.dispatchEvent(new CustomEvent('close', { bubbles: true, composed: true }));
  }

  private handleContentStyle(e: Event) {
    this.contentStyle = (e.target as HTMLSelectElement).value as ContentStyle;
    setAIConfig({ contentStyle: this.contentStyle });
  }

  private handlePerformance(e: Event) {
    this.performanceMode = (e.target as HTMLSelectElement).value as PerformanceMode;
    setAIConfig({ performanceMode: this.performanceMode });
  }

  private handleWebSearch() {
    this.webSearch = !this.webSearch;
    setAIConfig({ webSearch: this.webSearch });
  }

  private handleHistory() {
    this.conversationHistory = !this.conversationHistory;
    setAIConfig({ conversationHistory: this.conversationHistory });
  }

  private handleMaxHistory(e: Event) {
    const val = parseInt((e.target as HTMLInputElement).value, 10);
    if (!isNaN(val) && val >= 0 && val <= 100) {
      this.maxHistoryMessages = val;
      setAIConfig({ maxHistoryMessages: val });
    }
  }


  render() {
    if (!this.open) return nothing;

    return html`
      <div class="backdrop" @click=${this.close}></div>
      <aside class="panel" role="dialog" aria-label="Settings">
        <div class="panel-header">
          <h2 class="panel-title">Settings</h2>
          <button class="close-btn" @click=${this.close} aria-label="Close settings">
            <svg viewBox="0 0 24 24" fill="currentColor">
              <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
            </svg>
          </button>
        </div>

        <div class="panel-body">
          <!-- ── Tools ──────────────────────────────── -->
          <div class="section">
            <p class="section-label">Tools</p>

            <!-- Content Style -->
            <div class="field">
              <div class="field-row">
                <div class="field-info">
                  <p class="field-label">Content Style</p>
                  <p class="field-desc">How responses are structured and presented</p>
                </div>
                <select
                  class="field-select"
                  @change=${this.handleContentStyle}
                  aria-label="Content style"
                >
                  <option value="auto" ?selected=${this.contentStyle === 'auto'}>Auto</option>
                  ${this.styles.map(
                    (s) => html`<option value=${s.id} ?selected=${this.contentStyle === s.id}>${s.name}</option>`,
                  )}
                </select>
              </div>
            </div>

            <!-- Performance -->
            <div class="field">
              <div class="field-row">
                <div class="field-info">
                  <p class="field-label">Performance</p>
                  <p class="field-desc">Controls token usage, context, and cost</p>
                </div>
                <select
                  class="field-select"
                  @change=${this.handlePerformance}
                  aria-label="Performance mode"
                >
                  <option value="auto" ?selected=${this.performanceMode === 'auto'}>Auto</option>
                  <option value="comprehensive" ?selected=${this.performanceMode === 'comprehensive'}>Comprehensive</option>
                  <option value="optimized" ?selected=${this.performanceMode === 'optimized'}>Optimized</option>
                </select>
              </div>
            </div>

            <!-- Web Search -->
            <div class="field">
              <div class="field-row">
                <div class="field-info">
                  <p class="field-label">Web Search</p>
                  <p class="field-desc">Search the web for current information</p>
                </div>
                <label class="toggle">
                  <input
                    type="checkbox"
                    .checked=${this.webSearch}
                    @change=${this.handleWebSearch}
                  />
                  <span class="toggle-track"></span>
                </label>
              </div>
            </div>
          </div>

          <div class="divider"></div>

          <!-- ── Conversation ───────────────────────── -->
          <div class="section">
            <p class="section-label">Conversation</p>

            <!-- History -->
            <div class="field">
              <div class="field-row">
                <div class="field-info">
                  <p class="field-label">History</p>
                  <p class="field-desc">Include previous messages for context</p>
                </div>
                <label class="toggle">
                  <input
                    type="checkbox"
                    .checked=${this.conversationHistory}
                    @change=${this.handleHistory}
                  />
                  <span class="toggle-track"></span>
                </label>
              </div>
            </div>

            <!-- Max History -->
            <div class="field">
              <div class="field-row">
                <div class="field-info">
                  <p class="field-label">Max Messages</p>
                  <p class="field-desc">Maximum previous messages to include</p>
                </div>
                <input
                  type="number"
                  class="field-number"
                  min="0"
                  max="100"
                  .value=${String(this.maxHistoryMessages)}
                  @change=${this.handleMaxHistory}
                  aria-label="Maximum history messages"
                />
              </div>
            </div>
          </div>

        </div>
      </aside>
    `;
  }
}
