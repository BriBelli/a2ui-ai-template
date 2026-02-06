/**
 * A2UI Chat Configuration
 * 
 * Centralized configuration for UI behaviors, styles, and AI features.
 * Import and modify these settings to customize the chat experience.
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
   * Show suggestion prompts on the welcome screen.
   * Data is provided separately — this just toggles visibility.
   */
  suggestions: boolean;
}

export interface AIConfig {
  /**
   * Send conversation history with each message
   * Enables context-aware responses and follow-up questions
   */
  conversationHistory: boolean;

  /**
   * Maximum number of previous messages to include
   */
  maxHistoryMessages: number;

  /**
   * Enable web search tool for real-time information
   * Requires TAVILY_API_KEY on backend
   */
  webSearch: boolean;
}

/**
 * Default UI configuration
 */
export const uiConfig: UIConfig = {
  loadingStyle: 'chat',
  animateMessages: true,
  animateWelcome: true,
  suggestions: true,
};

/**
 * Default AI configuration
 */
export const aiConfig: AIConfig = {
  conversationHistory: true,
  maxHistoryMessages: 20,
  webSearch: true,
};

/**
 * Update UI configuration at runtime
 */
export function setUIConfig(config: Partial<UIConfig>): void {
  Object.assign(uiConfig, config);
}

/**
 * Update AI configuration at runtime
 */
export function setAIConfig(config: Partial<AIConfig>): void {
  Object.assign(aiConfig, config);
}
