/**
 * A2UI Chat UI Configuration
 * 
 * Centralized configuration for UI behaviors and styles.
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
}

/**
 * Default UI configuration
 */
export const uiConfig: UIConfig = {
  loadingStyle: 'subtle',
  animateMessages: true,
  animateWelcome: true,
};

/**
 * Update UI configuration at runtime
 */
export function setUIConfig(config: Partial<UIConfig>): void {
  Object.assign(uiConfig, config);
}
