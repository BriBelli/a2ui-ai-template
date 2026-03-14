import { LitElement, html, css, nothing } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import {
  aiConfig,
  uiConfig,
  setAIConfig,
  setUIConfig,
  type ContentStyle,
  type DashboardTier,
  type LoadingDetail,
  type LoadingStyle,
  type PerformanceMode,
  type SourcesPosition,
} from '../config/ui-config';
import type { SelectGroup } from './a2ui-model-selector';
import {
  dataSourceRegistry,
  type DataSourceInfo,
  type SourceStatus,
} from '../services/data-source-registry';

export type SettingsTab = 'settings' | 'data-sources' | 'dashboard';

interface StyleOption {
  id: string;
  name: string;
  description: string;
}

interface ToolState {
  id: string;
  name: string;
  description: string;
  default: boolean;
  env_override: boolean | null;
  locked: boolean;
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
      from {
        opacity: 0;
      }
      to {
        opacity: 1;
      }
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
      from {
        transform: translateX(100%);
      }
      to {
        transform: translateX(0);
      }
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
      transition:
        background-color var(--a2ui-transition-fast),
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

    /* ── Tab bar ───────────────────────────────────────── */

    .tab-bar {
      display: flex;
      border-bottom: 1px solid var(--a2ui-border-subtle);
      flex-shrink: 0;
      padding: 0 var(--a2ui-space-6);
      gap: var(--a2ui-space-1);
    }

    .tab-btn {
      display: flex;
      align-items: center;
      gap: var(--a2ui-space-2);
      padding: var(--a2ui-space-3) var(--a2ui-space-3);
      background: none;
      border: none;
      border-bottom: 2px solid transparent;
      font-family: var(--a2ui-font-family);
      font-size: var(--a2ui-text-sm);
      font-weight: var(--a2ui-font-medium);
      color: var(--a2ui-text-tertiary);
      cursor: pointer;
      transition:
        color var(--a2ui-transition-fast),
        border-color var(--a2ui-transition-fast);
      white-space: nowrap;
    }

    .tab-btn:hover {
      color: var(--a2ui-text-primary);
    }

    .tab-btn.active {
      color: var(--a2ui-accent);
      border-bottom-color: var(--a2ui-accent);
    }

    .tab-btn svg {
      width: 14px;
      height: 14px;
      flex-shrink: 0;
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
      transition:
        border-color var(--a2ui-transition-fast),
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
      transition:
        background-color 0.2s ease,
        border-color 0.2s ease;
    }

    .toggle-track::after {
      content: "";
      position: absolute;
      top: 2px;
      left: 2px;
      width: 16px;
      height: 16px;
      background: var(--a2ui-text-secondary);
      border-radius: 50%;
      transition:
        transform 0.2s ease,
        background-color 0.2s ease;
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
      transition:
        border-color var(--a2ui-transition-fast),
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

    /* ── Locked tool indicator ─────────────────────────── */

    .field.locked {
      opacity: 0.5;
      pointer-events: none;
    }

    .locked-badge {
      font-size: 9px;
      font-weight: var(--a2ui-font-semibold);
      color: var(--a2ui-text-tertiary);
      text-transform: uppercase;
      letter-spacing: 0.06em;
      background: var(--a2ui-bg-tertiary);
      border-radius: var(--a2ui-radius-sm);
      padding: 1px 5px;
      margin-left: var(--a2ui-space-2);
    }

    /* ── Divider ───────────────────────────────────────── */

    .divider {
      height: 1px;
      background: var(--a2ui-border-subtle);
      margin: var(--a2ui-space-6) 0;
    }

    /* ── Data Source Cards ──────────────────────────────── */

    .ds-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: var(--a2ui-space-4);
    }

    .ds-count {
      font-size: var(--a2ui-text-xs);
      color: var(--a2ui-text-tertiary);
    }

    .ds-list {
      display: flex;
      flex-direction: column;
      gap: 0;
      border: 1px solid var(--a2ui-border-subtle);
      overflow: hidden;
      margin: 0 -27px;;
    }

    .ds-card {
      display: flex;
      align-items: flex-start;
      gap: var(--a2ui-space-3);
      padding: var(--a2ui-space-3) var(--a2ui-space-4);
      background: var(--a2ui-bg-primary);
      border: none;
      border-left: 3px solid transparent;
      border-bottom: 1px solid var(--a2ui-border-subtle);
      cursor: pointer;
      transition:
        background-color 0.1s ease,
        border-left-color 0.2s ease;
      text-align: left;
      font-family: var(--a2ui-font-family);
      width: 100%;
    }

    .ds-card:last-child {
      border-bottom: none;
    }

    .ds-card:hover {
      background: var(--a2ui-bg-hover);
    }

    /* AI-active: blue left accent border — "this is in the response you're viewing" */
    .ds-card.ai-active {
      border-left-color: var(--a2ui-accent);
      background: rgba(138, 180, 248, 0.04);
    }

    .ds-card.unavailable {
      opacity: 0.45;
      cursor: default;
    }

    .ds-card.unavailable:hover {
      background: var(--a2ui-bg-primary);
    }

    .ds-check {
      width: 20px;
      height: 20px;
      flex-shrink: 0;
      margin-top: 1px;
      transition: color 0.15s ease;
    }

    /* AI auto-selected — blue check */
    .ds-check.ai-active {
      color: var(--a2ui-accent);
    }

    /* User pinned — green check */
    .ds-check.user-pinned {
      color: var(--a2ui-success, #81c995);
    }

    /* Both AI + user pinned — green check (border shows AI) */
    .ds-check.ai-active-pinned {
      color: var(--a2ui-success, #81c995);
    }

    .ds-check.inactive {
      color: var(--a2ui-text-tertiary);
    }

    .ds-check.unavailable {
      color: var(--a2ui-text-tertiary);
      opacity: 0.5;
    }

    .ds-info {
      flex: 1;
      min-width: 0;
    }

    .ds-name {
      display: flex;
      align-items: center;
      gap: var(--a2ui-space-2);
      font-size: var(--a2ui-text-sm);
      font-weight: var(--a2ui-font-medium);
      color: var(--a2ui-text-primary);
      margin: 0;
      line-height: 1.3;
    }

    .ds-card.unavailable .ds-name {
      text-decoration: line-through;
    }

    /* Status badges next to name — "IN USE" (blue) / "PINNED" (green) */
    .ds-status-badge {
      font-size: 9px;
      font-weight: var(--a2ui-font-semibold);
      text-transform: uppercase;
      letter-spacing: 0.04em;
      padding: 1px 5px;
      border-radius: var(--a2ui-radius-sm);
      line-height: 1.3;
      white-space: nowrap;
    }

    .ds-status-badge.in-use {
      background: rgba(138, 180, 248, 0.15);
      color: var(--a2ui-accent);
    }

    .ds-status-badge.pinned {
      background: rgba(129, 201, 149, 0.15);
      color: var(--a2ui-success, #81c995);
    }

    .ds-desc {
      font-size: var(--a2ui-text-xs);
      color: var(--a2ui-text-tertiary);
      margin: 2px 0 0;
      line-height: 1.3;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .ds-meta {
      display: flex;
      align-items: center;
      gap: var(--a2ui-space-2);
      margin-top: 3px;
    }

    .ds-badge {
      font-size: 10px;
      font-weight: var(--a2ui-font-medium);
      padding: 1px 6px;
      border-radius: var(--a2ui-radius-sm);
      line-height: 1.4;
    }

    .ds-badge.available {
      background: rgba(129, 201, 149, 0.15);
      color: var(--a2ui-success, #81c995);
    }

    .ds-badge.unavailable {
      background: var(--a2ui-bg-tertiary);
      color: var(--a2ui-text-tertiary);
    }

    .ds-badge.endpoints {
      background: var(--a2ui-bg-tertiary);
      color: var(--a2ui-text-tertiary);
    }

    .ds-empty {
      text-align: center;
      padding: var(--a2ui-space-8) var(--a2ui-space-4);
      color: var(--a2ui-text-tertiary);
      font-size: var(--a2ui-text-sm);
    }

    .ds-empty svg {
      width: 40px;
      height: 40px;
      margin-bottom: var(--a2ui-space-3);
      opacity: 0.4;
    }

    .ds-loading {
      display: flex;
      align-items: center;
      justify-content: center;
      padding: var(--a2ui-space-8);
    }

    .ds-loading .spinner {
      width: 20px;
      height: 20px;
      border: 2px solid var(--a2ui-border-default);
      border-top-color: var(--a2ui-accent);
      border-radius: 50%;
      animation: spin 0.7s linear infinite;
    }

    @keyframes spin {
      to {
        transform: rotate(360deg);
      }
    }

    /* ── Header actions (pin + close) ──────────────────── */

    .header-actions {
      display: flex;
      align-items: center;
      gap: var(--a2ui-space-1);
    }

    .pin-btn {
      width: 32px;
      height: 32px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: none;
      border: none;
      border-radius: var(--a2ui-radius-md);
      color: var(--a2ui-text-tertiary);
      cursor: pointer;
      transition:
        background-color var(--a2ui-transition-fast),
        color var(--a2ui-transition-fast);
    }

    .pin-btn:hover {
      background: var(--a2ui-bg-hover);
      color: var(--a2ui-text-primary);
    }

    .pin-btn.pinned {
      color: var(--a2ui-accent);
    }

    .pin-btn svg {
      width: 16px;
      height: 16px;
    }

    /* ── Inline mode (docked inside parent container) ── */

    :host([inline]) {
      height: 100%;
      overflow: hidden;
    }

    :host([inline]) .backdrop {
      display: none;
    }

    :host([inline]) .panel {
      position: relative;
      top: auto;
      right: auto;
      bottom: auto;
      width: 100%;
      height: 100%;
      max-width: none;
      box-shadow: none;
      border-left: none;
      animation: none;
      z-index: auto;
      min-height: 0;
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

      .tab-bar {
        padding: 0 var(--a2ui-space-4);
      }
    }
  `;

  @property({ type: Boolean }) open = false;
  @property({ type: String }) activeTab: SettingsTab = 'settings';
  @property({ type: Array }) modelGroups: SelectGroup[] = [];
  @property({ type: String }) modelValue = '';

  /**
   * When true, renders without backdrop/fixed positioning — the panel
   * fills its parent container and is suitable for embedding inline
   * (e.g. inside a docked workspace panel).
   */
  @property({ type: Boolean, reflect: true }) inline = false;

  /** Whether the panel is currently pinned/docked. Controls the pin icon state. */
  @property({ type: Boolean }) pinned = false;

  @state() private contentStyle: ContentStyle = aiConfig.contentStyle;
  @state() private performanceMode: PerformanceMode = aiConfig.performanceMode;
  @state() private loadingDetail: LoadingDetail = aiConfig.loadingDetail;
  @state() private loadingStyle: LoadingStyle = aiConfig.loadingStyle;
  @state() private webSearch = aiConfig.webSearch;
  @state() private geolocation = aiConfig.geolocation;
  @state() private dataSources = aiConfig.dataSources;
  @state() private smartRouting = aiConfig.smartRouting;
  @state() private temperature = aiConfig.temperature;
  @state() private conversationHistory = aiConfig.conversationHistory;
  @state() private maxHistoryMessages = aiConfig.maxHistoryMessages;
  @state() private showSources = uiConfig.showSources;
  @state() private showActions = uiConfig.showActions;
  @state() private sourcesPosition: SourcesPosition = uiConfig.sourcesPosition;
  @state() private streamingText = uiConfig.streamingText;
  @state() private dashboardTier: DashboardTier = uiConfig.dashboardTier;
  @state() private styleOptions: StyleOption[] = [];
  @state() private toolStates: Map<string, ToolState> = new Map();

  // ── Data Sources tab state ──────────────────────────────
  @state() private dsRegistry: DataSourceInfo[] = [];
  @state() private dsLoading = false;
  @state() private _dsVersion = 0; // bumped on registry change to trigger re-render

  private static _cachedStyleOptions: StyleOption[] | null = null;
  private static _cachedTools: ToolState[] | null = null;

  private _registryHandler = () => {
    this.dsRegistry = [...dataSourceRegistry.allSources];
    this._dsVersion++;
  };

  connectedCallback() {
    super.connectedCallback();
    this.syncFromConfig();
    if (A2UISettingsPanel._cachedStyleOptions) {
      this.styleOptions = A2UISettingsPanel._cachedStyleOptions;
    } else {
      this.fetchStyles();
    }
    if (A2UISettingsPanel._cachedTools) {
      this.toolStates = new Map(
        A2UISettingsPanel._cachedTools.map((t) => [t.id, t])
      );
    } else {
      this.fetchTools();
    }

    // Subscribe to registry changes
    dataSourceRegistry.addEventListener('change', this._registryHandler);
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    dataSourceRegistry.removeEventListener('change', this._registryHandler);
  }

  private syncFromConfig() {
    this.contentStyle = aiConfig.contentStyle;
    this.performanceMode = aiConfig.performanceMode;
    this.loadingDetail = aiConfig.loadingDetail;
    this.loadingStyle = aiConfig.loadingStyle;
    this.webSearch = aiConfig.webSearch;
    this.geolocation = aiConfig.geolocation;
    this.dataSources = aiConfig.dataSources;
    this.smartRouting = aiConfig.smartRouting;
    this.temperature = aiConfig.temperature;
    this.conversationHistory = aiConfig.conversationHistory;
    this.maxHistoryMessages = aiConfig.maxHistoryMessages;
    this.showSources = uiConfig.showSources;
    this.showActions = uiConfig.showActions;
    this.sourcesPosition = uiConfig.sourcesPosition;
    this.streamingText = uiConfig.streamingText;
    this.dashboardTier = uiConfig.dashboardTier;
  }

  private isToolLocked(toolId: string): boolean {
    return this.toolStates.get(toolId)?.locked ?? false;
  }

  private async fetchStyles() {
    try {
      const resp = await fetch('/api/styles');
      if (resp.ok) {
        const data = await resp.json();
        this.styleOptions = data.styles ?? [];
        A2UISettingsPanel._cachedStyleOptions = this.styleOptions;
      }
    } catch {
      this.styleOptions = [
        {
          id: 'analytical',
          name: 'Analytical',
          description: 'Data dashboards',
        },
        {
          id: 'content',
          name: 'Content',
          description: 'Narrative & editorial',
        },
        {
          id: 'comparison',
          name: 'Comparison',
          description: 'Side-by-side analysis',
        },
        {
          id: 'dashboard',
          name: 'Dashboard',
          description: 'Modern analytical dashboard',
        },
        { id: 'howto', name: 'How-To', description: 'Step-by-step guides' },
        { id: 'quick', name: 'Quick Answer', description: 'Concise responses' },
      ];
    }
  }

  private async fetchTools() {
    try {
      const resp = await fetch('/api/tools');
      if (resp.ok) {
        const data = await resp.json();
        const tools: ToolState[] = data.tools ?? [];
        A2UISettingsPanel._cachedTools = tools;
        this.toolStates = new Map(tools.map((t) => [t.id, t]));
      }
    } catch {
      // tools endpoint unavailable — no locking
    }
  }

  private async fetchDataSources() {
    if (dataSourceRegistry.fetched) {
      this.dsRegistry = [...dataSourceRegistry.allSources];
      return;
    }
    this.dsLoading = true;
    await dataSourceRegistry.fetchSources();
    this.dsRegistry = [...dataSourceRegistry.allSources];
    this.dsLoading = false;
  }

  updated(changed: Map<string, unknown>) {
    if (changed.has('open') && this.open) {
      this.syncFromConfig();
      // Eagerly fetch data sources if switching to that tab (or preload)
      if (!dataSourceRegistry.fetched) {
        this.fetchDataSources();
      } else {
        this.dsRegistry = [...dataSourceRegistry.allSources];
      }
    }
    if (changed.has('activeTab') && this.activeTab === 'data-sources') {
      if (!dataSourceRegistry.fetched) {
        this.fetchDataSources();
      }
    }
  }

  private close() {
    this.dispatchEvent(
      new CustomEvent('close', { bubbles: true, composed: true })
    );
  }

  private togglePin() {
    this.dispatchEvent(
      new CustomEvent('pin-toggle', {
        detail: { pinned: !this.pinned },
        bubbles: true,
        composed: true,
      })
    );
  }

  private handleModelChange(e: Event) {
    const value = (e.target as HTMLSelectElement).value;
    this.dispatchEvent(
      new CustomEvent('model-change', {
        detail: { value },
        bubbles: true,
        composed: true,
      })
    );
  }

  private handleContentStyle(e: Event) {
    this.contentStyle = (e.target as HTMLSelectElement).value as ContentStyle;
    setAIConfig({ contentStyle: this.contentStyle });
  }

  private handlePerformance(e: Event) {
    this.performanceMode = (e.target as HTMLSelectElement)
      .value as PerformanceMode;
    setAIConfig({ performanceMode: this.performanceMode });
  }

  private handleLoadingDetail(e: Event) {
    this.loadingDetail = (e.target as HTMLSelectElement).value as LoadingDetail;
    setAIConfig({ loadingDetail: this.loadingDetail });
  }

  private handleLoadingStyle(e: Event) {
    this.loadingStyle = (e.target as HTMLSelectElement).value as LoadingStyle;
    setAIConfig({ loadingStyle: this.loadingStyle });
  }

  private handleWebSearch() {
    if (this.isToolLocked('web_search')) return;
    this.webSearch = !this.webSearch;
    setAIConfig({ webSearch: this.webSearch });
  }

  private handleGeolocation() {
    if (this.isToolLocked('geolocation')) return;
    this.geolocation = !this.geolocation;
    setAIConfig({ geolocation: this.geolocation });
  }

  private handleDataSources() {
    if (this.isToolLocked('data_sources')) return;
    this.dataSources = !this.dataSources;
    setAIConfig({ dataSources: this.dataSources });
  }

  private handleSmartRouting() {
    this.smartRouting = !this.smartRouting;
    setAIConfig({ smartRouting: this.smartRouting });
  }

  private handleTemperature(e: Event) {
    const val = parseFloat((e.target as HTMLInputElement).value);
    if (!isNaN(val) && val >= 0 && val <= 2) {
      this.temperature = Math.round(val * 10) / 10; // snap to 0.1 increments
      setAIConfig({ temperature: this.temperature });
    }
  }

  private handleHistory() {
    if (this.isToolLocked('history')) return;
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

  private handleShowSources() {
    this.showSources = !this.showSources;
    setUIConfig({ showSources: this.showSources });
  }

  private handleShowActions() {
    this.showActions = !this.showActions;
    setUIConfig({ showActions: this.showActions });
  }

  private handleStreamingText() {
    this.streamingText = !this.streamingText;
    setUIConfig({ streamingText: this.streamingText });
  }

  private handleDashboardTier() {
    const next: DashboardTier =
      this.dashboardTier === 'static' ? 'hybrid' : 'static';
    this.dashboardTier = next;
    setUIConfig({ dashboardTier: next });
    // Notify parent so it can update its own state
    this.dispatchEvent(
      new CustomEvent('dashboard-tier-change', {
        detail: { tier: next },
        bubbles: true,
        composed: true,
      })
    );
  }

  private handleSourcesPosition(e: Event) {
    this.sourcesPosition = (e.target as HTMLSelectElement)
      .value as SourcesPosition;
    setUIConfig({ sourcesPosition: this.sourcesPosition });
  }

  private handleToggleSource(id: string) {
    dataSourceRegistry.toggleSource(id);
    this._dsVersion++;
  }

  // ── Data Sources tab rendering ────────────────────────────

  private _getSourceStatus(id: string): SourceStatus {
    return dataSourceRegistry.getStatus(id);
  }

  private _renderCircleCheck(status: SourceStatus) {
    // User-pinned or both: green filled circle-check
    if (status === 'user-pinned' || status === 'ai-active+pinned') {
      const cssClass =
        status === 'ai-active+pinned' ? 'ai-active-pinned' : 'user-pinned';
      return html`
        <svg class="ds-check ${cssClass}" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
        </svg>
      `;
    }
    // AI auto-selected: blue filled circle-check
    if (status === 'ai-active') {
      return html`
        <svg class="ds-check ai-active" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
        </svg>
      `;
    }
    // Empty circle — grey (inactive / unavailable / disabled)
    return html`
      <svg class="ds-check ${status}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="9"/>
      </svg>
    `;
  }

  private renderDataSourcesTab() {
    if (this.dsLoading) {
      return html`
        <div class="ds-loading">
          <div class="spinner"></div>
        </div>
      `;
    }

    if (this.dsRegistry.length === 0) {
      return html`
        <div class="ds-empty">
          <svg viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 3C7.58 3 4 4.79 4 7v10c0 2.21 3.58 4 8 4s8-1.79 8-4V7c0-2.21-3.58-4-8-4zm6 14c0 .5-2.13 2-6 2s-6-1.5-6-2v-2.34c1.52 1.1 4.28 1.84 8 1.84s6.48-.75 8-1.84V17zm0-5c0 .5-2.13 2-6 2s-6-1.5-6-2V9.66c1.52 1.1 4.28 1.84 8 1.84s6.48-.75 8-1.84V12zm-6-3c-3.87 0-6-1.5-6-2s2.13-2 6-2 6 1.5 6 2-2.13 2-6 2z"/>
          </svg>
          <p>No data sources registered</p>
          <p style="font-size: var(--a2ui-text-xs); margin-top: var(--a2ui-space-1);">
            Configure sources in the backend YAML configs
          </p>
        </div>
      `;
    }

    // Force re-render when _dsVersion changes (used by toggle)
    void this._dsVersion;

    // Count breakdown
    let inUseCount = 0;
    let pinnedCount = 0;
    for (const src of this.dsRegistry) {
      const st = this._getSourceStatus(src.id);
      if (st === 'ai-active' || st === 'ai-active+pinned') inUseCount++;
      if (st === 'user-pinned' || st === 'ai-active+pinned') pinnedCount++;
    }

    return html`
      <div class="ds-header">
        <p class="section-label" style="margin: 0;">Data Sources</p>
        <span class="ds-count">
          ${inUseCount > 0 ? html`${inUseCount} in use` : nothing}${
      inUseCount > 0 && pinnedCount > 0 ? html` · ` : nothing
    }${pinnedCount > 0 ? html`${pinnedCount} pinned` : nothing}${
      inUseCount === 0 && pinnedCount === 0 ? html`0 active` : nothing
    } / ${this.dsRegistry.length} total
        </span>
      </div>

      <div class="ds-list">
        ${this.dsRegistry.map((src) => {
          const status = this._getSourceStatus(src.id);
          const isUnavailable = status === 'unavailable';
          const isAiActive =
            status === 'ai-active' || status === 'ai-active+pinned';
          const isPinned =
            status === 'user-pinned' || status === 'ai-active+pinned';

          return html`
            <button
              class="ds-card ${isUnavailable ? 'unavailable' : ''} ${
            isAiActive ? 'ai-active' : ''
          }"
              @click=${() => !isUnavailable && this.handleToggleSource(src.id)}
              ?disabled=${isUnavailable}
              title=${
                isUnavailable
                  ? `${src.name} is not available (check backend config)`
                  : isPinned
                  ? `${src.name} is pinned by you — click to unpin`
                  : isAiActive
                  ? `AI is using ${src.name} — Click to pin it for future queries`
                  : `Click to pin ${src.name} for future queries`
              }
            >
              ${this._renderCircleCheck(status)}
              <div class="ds-info">
                <p class="ds-name">
                  <span>${src.name}</span>
                  ${
                    isAiActive
                      ? html`<span class="ds-status-badge in-use">In Use</span>`
                      : nothing
                  }
                  ${
                    isPinned
                      ? html`<span class="ds-status-badge pinned">Pinned</span>`
                      : nothing
                  }
                </p>
                ${
                  src.description
                    ? html`<p class="ds-desc">${src.description}</p>`
                    : nothing
                }
                <div class="ds-meta">
                  ${
                    src.available
                      ? html`<span class="ds-badge available">Available</span>`
                      : html`<span class="ds-badge unavailable">Unavailable</span>`
                  }
                  ${
                    src.endpointCount > 0
                      ? html`<span class="ds-badge endpoints">${src.endpointCount} endpoints</span>`
                      : nothing
                  }
                </div>
              </div>
            </button>
          `;
        })}
      </div>
    `;
  }

  // ── Dashboard tab rendering ──────────────────────────────────

  private renderDashboardTab() {
    return html`
      <div class="section">
        <p class="section-label">Rendering Tier</p>

        <div class="field">
          <div class="field-row">
            <div class="field-info">
              <p class="field-label">Hybrid AI Mode</p>
              <p class="field-desc">
                ${
                  this.dashboardTier === 'hybrid'
                    ? 'AI generates dashboard layouts with strict shapes (low cost)'
                    : 'Static builders render dashboards instantly (no AI cost)'
                }
              </p>
            </div>
            <label class="toggle">
              <input
                type="checkbox"
                .checked=${this.dashboardTier === 'hybrid'}
                @change=${this.handleDashboardTier}
              />
              <span class="toggle-track"></span>
            </label>
          </div>
        </div>
      </div>
    `;
  }

  // ── Shared panel content (header + tabs + body) ────────────

  private renderPanelContent() {
    // Pin icon: pushpin rotated when pinned
    const pinIcon = this.pinned
      ? html`<svg viewBox="0 0 24 24" fill="currentColor"><path d="M16 12V4h1V2H7v2h1v8l-2 2v2h5.2v6h1.6v-6H18v-2l-2-2z"/></svg>`
      : html`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="17" x2="12" y2="22"/><path d="M5 17h14v-1.76a2 2 0 00-1.11-1.79l-1.78-.9A2 2 0 0115 10.76V6h1a2 2 0 000-4H8a2 2 0 000 4h1v4.76a2 2 0 01-1.11 1.79l-1.78.9A2 2 0 005 15.24V17z"/></svg>`;

    return html`
      <div class="panel-header">
        <h2 class="panel-title">
          ${
            this.activeTab === 'data-sources'
              ? 'Data Sources'
              : this.activeTab === 'dashboard'
              ? 'Dashboard'
              : 'Settings'
          }
        </h2>
        <div class="header-actions">
          <button
            class="pin-btn ${this.pinned ? 'pinned' : ''}"
            @click=${this.togglePin}
            title=${
              this.pinned
                ? 'Unpin panel (switch to overlay)'
                : 'Pin panel (dock to side)'
            }
            aria-label=${this.pinned ? 'Unpin panel' : 'Pin panel'}
          >
            ${pinIcon}
          </button>
          <button
            class="close-btn"
            @click=${this.close}
            aria-label="Close panel"
          >
            <svg viewBox="0 0 24 24" fill="currentColor">
              <path
                d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"
              />
            </svg>
          </button>
        </div>
      </div>

      <!-- Tab bar -->
      <div class="tab-bar" role="tablist">
        <button
          class="tab-btn ${this.activeTab === 'settings' ? 'active' : ''}"
          role="tab"
          aria-selected=${this.activeTab === 'settings'}
          @click=${() => (this.activeTab = 'settings')}
        >
          <svg viewBox="0 0 24 24" fill="currentColor">
            <path d="M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58a.49.49 0 00.12-.61l-1.92-3.32a.488.488 0 00-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54a.484.484 0 00-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.07.62-.07.94s.02.64.07.94l-2.03 1.58a.49.49 0 00-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6A3.6 3.6 0 1112 8.4a3.6 3.6 0 010 7.2z"/>
          </svg>
          Settings
        </button>
        <button
          class="tab-btn ${this.activeTab === 'data-sources' ? 'active' : ''}"
          role="tab"
          aria-selected=${this.activeTab === 'data-sources'}
          @click=${() => (this.activeTab = 'data-sources')}
        >
          <svg viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 3C7.58 3 4 4.79 4 7v10c0 2.21 3.58 4 8 4s8-1.79 8-4V7c0-2.21-3.58-4-8-4zm6 14c0 .5-2.13 2-6 2s-6-1.5-6-2v-2.34c1.52 1.1 4.28 1.84 8 1.84s6.48-.75 8-1.84V17zm0-5c0 .5-2.13 2-6 2s-6-1.5-6-2V9.66c1.52 1.1 4.28 1.84 8 1.84s6.48-.75 8-1.84V12zm-6-3c-3.87 0-6-1.5-6-2s2.13-2 6-2 6 1.5 6 2-2.13 2-6 2z"/>
          </svg>
          Data Sources
        </button>
        <button
          class="tab-btn ${this.activeTab === 'dashboard' ? 'active' : ''}"
          role="tab"
          aria-selected=${this.activeTab === 'dashboard'}
          @click=${() => (this.activeTab = 'dashboard')}
        >
          <svg viewBox="0 0 24 24" fill="currentColor">
            <path d="M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z"/>
          </svg>
          Dashboard
        </button>
      </div>

      <div class="panel-body">
        ${
          this.activeTab === 'settings'
            ? this.renderSettingsTab()
            : this.activeTab === 'dashboard'
            ? this.renderDashboardTab()
            : this.renderDataSourcesTab()
        }
      </div>
    `;
  }

  // ── Main render ──────────────────────────────────────────

  render() {
    if (!this.open) return nothing;

    const content = this.renderPanelContent();

    // Inline mode: no backdrop, no fixed positioning — fills parent
    if (this.inline) {
      return html`
        <aside class="panel" role="complementary" aria-label="Workspace Panel">
          ${content}
        </aside>
      `;
    }

    // Overlay mode: backdrop + fixed panel (original behavior)
    return html`
      <div class="backdrop" @click=${this.close}></div>
      <aside class="panel" role="dialog" aria-label="Settings">
        ${content}
      </aside>
    `;
  }

  // ── Settings tab (original content extracted) ──────────────

  private renderSettingsTab() {
    return html`
      <!-- ── Model ──────────────────────────────── -->
      ${
        this.modelGroups.length > 0
          ? html`
          <div class="section">
            <p class="section-label">Model</p>
            <div class="field">
              <div class="field-row">
                <div class="field-info">
                  <p class="field-label">Active Model</p>
                  <p class="field-desc">
                    Model used for generating responses
                  </p>
                </div>
                <select
                  class="field-select"
                  @change=${this.handleModelChange}
                  aria-label="Model"
                >
                  ${this.modelGroups.map((group) =>
                    group.label
                      ? html`<optgroup label=${group.label}>
                          ${group.items.map(
                            (item) =>
                              html`<option
                                value=${item.value}
                                ?selected=${item.value === this.modelValue}
                              >
                                ${item.label}
                              </option>`
                          )}
                        </optgroup>`
                      : group.items.map(
                          (item) =>
                            html`<option
                              value=${item.value}
                              ?selected=${item.value === this.modelValue}
                            >
                              ${item.label}
                            </option>`
                        )
                  )}
                </select>
              </div>
            </div>

            <!-- Smart Model Routing -->
            <div class="field">
              <div class="field-row">
                <div class="field-info">
                  <p class="field-label">Smart Model Routing</p>
                  <p class="field-desc">
                    Let the AI pick the best model based on task complexity
                  </p>
                </div>
                <label class="toggle">
                  <input
                    type="checkbox"
                    .checked=${this.smartRouting}
                    @change=${this.handleSmartRouting}
                  />
                  <span class="toggle-track"></span>
                </label>
              </div>
            </div>

            <!-- Temperature -->
            <div class="field">
              <div class="field-row">
                <div class="field-info">
                  <p class="field-label">Temperature</p>
                  <p class="field-desc">
                    Controls randomness (0 = deterministic, 2 = creative)
                  </p>
                </div>
                <input
                  type="number"
                  class="field-number"
                  min="0"
                  max="2"
                  step="0.1"
                  .value=${String(this.temperature)}
                  @change=${this.handleTemperature}
                  aria-label="Temperature"
                />
              </div>
            </div>
          </div>
        `
          : nothing
      }

      <div class="divider"></div>

      <!-- ── Tools ──────────────────────────────── -->
      <div class="section">
        <p class="section-label">Tools</p>

        <!-- Content Style -->
        <div class="field">
          <div class="field-row">
            <div class="field-info">
              <p class="field-label">Content Style</p>
              <p class="field-desc">
                How responses are structured and presented
              </p>
            </div>
            <select
              class="field-select"
              @change=${this.handleContentStyle}
              aria-label="Content style"
            >
              <option
                value="auto"
                ?selected=${this.contentStyle === 'auto'}
              >
                Auto
              </option>
              ${this.styleOptions.map(
                (s) =>
                  html`<option
                    value=${s.id}
                    ?selected=${this.contentStyle === s.id}
                  >
                    ${s.name}
                  </option>`
              )}
            </select>
          </div>
        </div>

        <!-- Performance -->
        <div class="field">
          <div class="field-row">
            <div class="field-info">
              <p class="field-label">Performance</p>
              <p class="field-desc">
                Controls token usage, context, and cost
              </p>
            </div>
            <select
              class="field-select"
              @change=${this.handlePerformance}
              aria-label="Performance mode"
            >
              <option
                value="auto"
                ?selected=${this.performanceMode === 'auto'}
              >
                Auto
              </option>
              <option
                value="comprehensive"
                ?selected=${this.performanceMode === 'comprehensive'}
              >
                Comprehensive
              </option>
              <option
                value="optimized"
                ?selected=${this.performanceMode === 'optimized'}
              >
                Optimized
              </option>
            </select>
          </div>
        </div>

        <!-- Web Search -->
        <div
          class="field ${this.isToolLocked('web_search') ? 'locked' : ''}"
        >
          <div class="field-row">
            <div class="field-info">
              <p class="field-label">
                Web
                Search${
                  this.isToolLocked('web_search')
                    ? html`<span class="locked-badge">Locked</span>`
                    : ''
                }
              </p>
              <p class="field-desc">
                Search the web for current information
              </p>
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

        <!-- Geolocation -->
        <div
          class="field ${this.isToolLocked('geolocation') ? 'locked' : ''}"
        >
          <div class="field-row">
            <div class="field-info">
              <p class="field-label">
                Geolocation${
                  this.isToolLocked('geolocation')
                    ? html`<span class="locked-badge">Locked</span>`
                    : ''
                }
              </p>
              <p class="field-desc">
                Use device location for weather and local queries
              </p>
            </div>
            <label class="toggle">
              <input
                type="checkbox"
                .checked=${this.geolocation}
                @change=${this.handleGeolocation}
              />
              <span class="toggle-track"></span>
            </label>
          </div>
        </div>

        <div
          class="field"
          style="opacity: ${this.isToolLocked('data_sources') ? '0.5' : '1'}"
        >
          <div class="field-row">
            <div class="field-info">
              <p class="field-label">
                Data
                Sources${
                  this.isToolLocked('data_sources')
                    ? html`<span class="locked-badge">Locked</span>`
                    : ''
                }
              </p>
              <p class="field-desc">
                Query configured external APIs and databases
              </p>
            </div>
            <label class="toggle">
              <input
                type="checkbox"
                .checked=${this.dataSources}
                @change=${this.handleDataSources}
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
        <div class="field ${this.isToolLocked('history') ? 'locked' : ''}">
          <div class="field-row">
            <div class="field-info">
              <p class="field-label">
                History${
                  this.isToolLocked('history')
                    ? html`<span class="locked-badge">Locked</span>`
                    : ''
                }
              </p>
              <p class="field-desc">
                Include previous messages for context
              </p>
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

      <div class="divider"></div>

      <!-- ── Display ─────────────────────────────── -->
      <div class="section">
        <p class="section-label">Display</p>
        <!-- Show Actions -->
        <div class="field">
          <div class="field-row">
            <div class="field-info">
              <p class="field-label">Action Bar</p>
              <p class="field-desc">
                Copy, regenerate, and feedback buttons
              </p>
            </div>
            <label class="toggle">
              <input
                type="checkbox"
                .checked=${this.showActions}
                @change=${this.handleShowActions}
              />
              <span class="toggle-track"></span>
            </label>
          </div>
        </div>
        <!-- Stream Response -->
        <div class="field">
          <div class="field-row">
            <div class="field-info">
              <p class="field-label">Stream Response</p>
              <p class="field-desc">
                Show AI text progressively as it generates
              </p>
            </div>
            <label class="toggle">
              <input
                type="checkbox"
                .checked=${this.streamingText}
                @change=${this.handleStreamingText}
              />
              <span class="toggle-track"></span>
            </label>
          </div>
        </div>
      </div>
      <!-- Show Sources -->
      <div class="field">
        <div class="field-row">
          <div class="field-info">
            <p class="field-label">Sources</p>
            <p class="field-desc">Show source citations below responses</p>
          </div>
          <label class="toggle">
            <input
              type="checkbox"
              .checked=${this.showSources}
              @change=${this.handleShowSources}
            />
            <span class="toggle-track"></span>
          </label>
        </div>
      </div>

      <!-- Sources Position -->
      <div class="field">
        <div class="field-row">
          <div class="field-info">
            <p class="field-label">Sources Position</p>
            <p class="field-desc">Where citation sources appear</p>
          </div>
          <select
            class="field-select"
            @change=${this.handleSourcesPosition}
            aria-label="Sources position"
          >
            <option
              value="auto"
              ?selected=${this.sourcesPosition === 'auto'}
            >
              Auto
            </option>
            <option
              value="right"
              ?selected=${this.sourcesPosition === 'right'}
            >
              Right
            </option>
            <option
              value="bottom"
              ?selected=${this.sourcesPosition === 'bottom'}
            >
              Bottom
            </option>
          </select>
        </div>
      </div>
      <!-- Loading Detail -->
        <div class="field">
          <div class="field-row">
            <div class="field-info">
              <p class="field-label">Loading Detail</p>
              <p class="field-desc">
                How much pipeline info the thinking indicator shows
              </p>
            </div>
            <select
              class="field-select"
              @change=${this.handleLoadingDetail}
              aria-label="Loading detail level"
            >
              <option
                value="basic"
                ?selected=${this.loadingDetail === 'basic'}
              >
                Basic
              </option>
              <option
                value="moderate"
                ?selected=${this.loadingDetail === 'moderate'}
              >
                Moderate
              </option>
              <option
                value="comprehensive"
                ?selected=${this.loadingDetail === 'comprehensive'}
              >
                Comprehensive
              </option>
              <option
                value="thought"
                ?selected=${this.loadingDetail === 'thought'}
              >
                Thought
              </option>
            </select>
          </div>
        </div>

        <!-- Loading Style -->
        <div class="field">
          <div class="field-row">
            <div class="field-info">
              <p class="field-label">Loading Style</p>
              <p class="field-desc">
                How pipeline steps are animated during loading
              </p>
            </div>
            <select
              class="field-select"
              @change=${this.handleLoadingStyle}
              aria-label="Loading animation style"
            >
              <option
                value="basic"
                ?selected=${this.loadingStyle === 'basic'}
              >
                Basic
              </option>
              <option
                value="focus"
                ?selected=${this.loadingStyle === 'focus'}
              >
                Focus
              </option>
              <option
                value="stack"
                ?selected=${this.loadingStyle === 'stack'}
              >
                Stack
              </option>
            </select>
          </div>
        </div>
    `;
  }
}
