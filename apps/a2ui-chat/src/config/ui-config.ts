/**
 * A2UI Chat Configuration
 * 
 * Centralized configuration for UI behaviors, styles, and AI features.
 * Settings are persisted to localStorage so they survive page reloads.
 */

export interface UIConfig {
  /**
   * Enable message entrance animations
   */
  animateMessages: boolean;

  /**
   * Enable welcome screen animations
   */
  animateWelcome: boolean;

  /**
   * Maximum number of suggestions to show (welcome screen + per-response).
   * 0 = off, 1 = one suggestion, 2 = two, etc.
   * Data is provided separately — this just caps how many are displayed.
   */
  maxSuggestions: number;

  /**
   * Persist chat threads to localStorage so conversations
   * survive page refreshes. Threads are scoped per user.
   */
  persistChat: boolean;

  /**
   * Show source citations below assistant responses
   */
  showSources: boolean;

  /**
   * Show action bar (copy, regenerate, like/dislike) on assistant responses
   */
  showActions: boolean;

  /**
   * Sources panel position relative to the response content.
   * - 'auto': Side-by-side on wide screens, collapses below on narrow (default)
   * - 'right': Always side-by-side
   * - 'bottom': Always below the content
   */
  sourcesPosition: SourcesPosition;

  /**
   * Show progressive token streaming in chat while the AI generates.
   * When enabled, response text streams character-by-character with a typing cursor.
   * When disabled, the thinking indicator stays visible until the full response arrives.
   * Backend SSE streaming always runs regardless — this only controls the UX.
   * Default: true.
   */
  streamingText: boolean;
}

export type SourcesPosition = 'auto' | 'right' | 'bottom';

export type ContentStyle = 'auto' | 'analytical' | 'content' | 'comparison' | 'dashboard' | 'howto' | 'quick';
export type PerformanceMode = 'auto' | 'comprehensive' | 'optimized';
export type LoadingDetail = 'basic' | 'moderate' | 'comprehensive' | 'thought';
export type LoadingStyle = 'basic' | 'focus' | 'stack';

export interface AIConfig {
  /**
   * Send conversation history with each message
   */
  conversationHistory: boolean;

  /**
   * Maximum number of previous messages to include
   */
  maxHistoryMessages: number;

  /**
   * Enable web search tool for real-time information
   */
  webSearch: boolean;

  /**
   * Enable geolocation for location-aware responses
   */
  geolocation: boolean;

  /**
   * Enable data sources tool for querying configured external APIs
   */
  dataSources: boolean;

  /**
   * Content style for response presentation.
   * - 'auto': Classify intent automatically (default)
   * - 'analytical': Data dashboards with KPIs, charts, tables
   * - 'content': Narrative/editorial with sections, lists, accordions
   * - 'comparison': Side-by-side analysis with charts and detail tables
   * - 'dashboard': Modern KPI cards, charts, and clean grid layout
   * - 'howto': Step-by-step instructions and procedural guides
   * - 'quick': Concise direct answers with minimal components
   */
  contentStyle: ContentStyle;

  /**
   * Performance mode controlling token usage, context size, and cost.
   * - 'auto': Adapts based on payload size (default)
   * - 'comprehensive': Full context, max tokens, all features
   * - 'optimized': Minimal context, fastest, cheapest
   */
  performanceMode: PerformanceMode;

  /**
   * Loading indicator detail level — controls what information is shown.
   * - 'basic': Just "Thinking..." with elapsed time
   * - 'moderate': Key pipeline steps (search, analyze, generate)
   * - 'comprehensive': All steps with timing and detail text
   * - 'thought': Chain-of-thought — all steps + reasoning in a collapsible panel
   */
  loadingDetail: LoadingDetail;

  /**
   * Loading indicator presentation style — controls how steps are animated.
   * - 'basic': Simple list, steps fade in and stay visible
   * - 'focus': Slot-machine — one step visible at a time, scrolls up on transition
   * - 'stack': All steps appended, scrollable with max-height
   */
  loadingStyle: LoadingStyle;

  /**
   * Allow the AI pipeline to dynamically route to a stronger or faster model
   * based on task complexity analysis. When disabled, the selected model is
   * always used as-is with no substitution.
   */
  smartRouting: boolean;
}

const SETTINGS_KEY = 'a2ui_settings';

/**
 * Default UI configuration
 */
export const uiConfig: UIConfig = {
  animateMessages: true,
  animateWelcome: true,
  maxSuggestions: 3,
  persistChat: true,
  showSources: true,
  showActions: true,
  sourcesPosition: 'auto',
  streamingText: true,
};

/**
 * Default AI configuration
 */
export const aiConfig: AIConfig = {
  conversationHistory: true,
  maxHistoryMessages: 20,
  webSearch: true,
  geolocation: true,
  dataSources: true,
  contentStyle: 'auto',
  performanceMode: 'auto',
  loadingDetail: 'moderate',
  loadingStyle: 'focus',
  smartRouting: true,
};

const VALID_CONTENT_STYLES: ReadonlySet<ContentStyle> = new Set([
  'auto', 'analytical', 'content', 'comparison', 'dashboard', 'howto', 'quick',
]);
const VALID_PERFORMANCE_MODES: ReadonlySet<PerformanceMode> = new Set([
  'auto', 'comprehensive', 'optimized',
]);
const VALID_LOADING_DETAILS: ReadonlySet<LoadingDetail> = new Set([
  'basic', 'moderate', 'comprehensive', 'thought',
]);
const VALID_LOADING_STYLES: ReadonlySet<LoadingStyle> = new Set([
  'basic', 'focus', 'stack',
]);
const VALID_SOURCES_POSITIONS: ReadonlySet<SourcesPosition> = new Set([
  'auto', 'right', 'bottom',
]);

/**
 * Load persisted settings from localStorage (call once at startup).
 * Validates saved values to prevent stale/invalid settings from persisting.
 */
export function loadSettings(): void {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY);
    if (!raw) return;
    const saved = JSON.parse(raw);
    if (saved.ai) {
      Object.assign(aiConfig, saved.ai);
      if (!VALID_CONTENT_STYLES.has(aiConfig.contentStyle)) {
        aiConfig.contentStyle = 'auto';
      }
      if (!VALID_PERFORMANCE_MODES.has(aiConfig.performanceMode)) {
        aiConfig.performanceMode = 'auto';
      }
      if (!VALID_LOADING_DETAILS.has(aiConfig.loadingDetail)) {
        aiConfig.loadingDetail = 'moderate';
      }
      if (!VALID_LOADING_STYLES.has(aiConfig.loadingStyle)) {
        aiConfig.loadingStyle = 'focus';
      }
    }
    if (saved.ui) {
      Object.assign(uiConfig, saved.ui);
      if (!VALID_SOURCES_POSITIONS.has(uiConfig.sourcesPosition)) {
        uiConfig.sourcesPosition = 'auto';
      }
    }
  } catch {
    // corrupted storage — use defaults
  }
}

/**
 * Persist current settings to localStorage.
 */
export function saveSettings(): void {
  try {
    localStorage.setItem(
      SETTINGS_KEY,
      JSON.stringify({ ai: aiConfig, ui: uiConfig }),
    );
  } catch {
    // quota exceeded or private browsing — silently ignore
  }
}

/**
 * Update AI configuration at runtime and persist.
 */
export function setAIConfig(config: Partial<AIConfig>): void {
  Object.assign(aiConfig, config);
  saveSettings();
}

/**
 * Update UI configuration at runtime and persist.
 */
export function setUIConfig(config: Partial<UIConfig>): void {
  Object.assign(uiConfig, config);
  saveSettings();
}
