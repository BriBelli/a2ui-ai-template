/**
 * A2UI Chat Configuration
 * 
 * Centralized configuration for UI behaviors, styles, and AI features.
 * Settings are persisted to localStorage so they survive page reloads.
 */

export type LoadingStyle = 'chat' | 'subtle';

export interface UIConfig {
  /**
   * Loading indicator style
   * - 'chat': Full message-style with AI avatar and bubble
   * - 'subtle': Minimal dots with text
   */
  loadingStyle: LoadingStyle;

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
}

export type ContentStyle = 'auto' | 'analytical' | 'content' | 'comparison' | 'howto' | 'quick';
export type PerformanceMode = 'auto' | 'comprehensive' | 'optimized';
export type LoadingDisplay = 'comprehensive' | 'moderate' | 'basic';

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
   * Content style for response presentation.
   * - 'auto': Classify intent automatically (default)
   * - 'analytical': Data dashboards with KPIs, charts, tables
   * - 'content': Narrative/editorial with sections, lists, accordions
   * - 'comparison': Side-by-side analysis with charts and detail tables
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
   * Loading indicator detail level.
   * - 'comprehensive': All tools, timing, search queries, model info
   * - 'moderate': Active tools and key outcomes (default)
   * - 'basic': Just "Thinking..." with elapsed time
   */
  loadingDisplay: LoadingDisplay;
}

const SETTINGS_KEY = 'a2ui_settings';

/**
 * Default UI configuration
 */
export const uiConfig: UIConfig = {
  loadingStyle: 'chat',
  animateMessages: true,
  animateWelcome: true,
  maxSuggestions: 3,
  persistChat: true,
};

/**
 * Default AI configuration
 */
export const aiConfig: AIConfig = {
  conversationHistory: true,
  maxHistoryMessages: 20,
  webSearch: true,
  geolocation: true,
  contentStyle: 'auto',
  performanceMode: 'auto',
  loadingDisplay: 'moderate',
};

const VALID_CONTENT_STYLES: ReadonlySet<ContentStyle> = new Set([
  'auto', 'analytical', 'content', 'comparison', 'howto', 'quick',
]);
const VALID_PERFORMANCE_MODES: ReadonlySet<PerformanceMode> = new Set([
  'auto', 'comprehensive', 'optimized',
]);
const VALID_LOADING_DISPLAYS: ReadonlySet<LoadingDisplay> = new Set([
  'comprehensive', 'moderate', 'basic',
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
      if (!VALID_LOADING_DISPLAYS.has(aiConfig.loadingDisplay)) {
        aiConfig.loadingDisplay = 'moderate';
      }
    }
    if (saved.ui) Object.assign(uiConfig, saved.ui);
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
