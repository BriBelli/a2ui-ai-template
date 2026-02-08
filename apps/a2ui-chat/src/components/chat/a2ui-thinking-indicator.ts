import { LitElement, html, css } from 'lit';
import { customElement, property } from 'lit/decorators.js';

export interface ThinkingStep {
  label: string;
  done: boolean;
}

@customElement('a2ui-thinking-indicator')
export class A2UIThinkingIndicator extends LitElement {
  static styles = css`
    :host {
      display: block;
    }

    .thinking {
      display: flex;
      align-items: flex-start;
      gap: var(--a2ui-space-3);
      padding: var(--a2ui-space-4) 0;
      animation: fadeIn 0.3s ease forwards;
    }

    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(8px); }
      to { opacity: 1; transform: translateY(0); }
    }

    .avatar {
      width: 32px;
      height: 32px;
      border-radius: var(--a2ui-radius-full);
      background: linear-gradient(135deg, #4285f4, #ea4335, #fbbc05, #34a853);
      display: flex;
      align-items: center;
      justify-content: center;
      color: white;
      font-size: var(--a2ui-text-sm);
      font-weight: var(--a2ui-font-medium);
      flex-shrink: 0;
    }

    .content {
      display: flex;
      flex-direction: column;
      gap: var(--a2ui-space-2);
      min-width: 0;
    }

    .header {
      display: flex;
      align-items: center;
      gap: var(--a2ui-space-2);
      color: var(--a2ui-text-secondary);
      font-size: var(--a2ui-text-sm);
    }

    .spinner {
      width: 14px;
      height: 14px;
      border: 2px solid var(--a2ui-border-default);
      border-top-color: var(--a2ui-accent);
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }

    @keyframes spin {
      to { transform: rotate(360deg); }
    }

    .steps {
      display: flex;
      flex-direction: column;
      gap: var(--a2ui-space-1);
      padding-left: var(--a2ui-space-1);
    }

    .step {
      display: flex;
      align-items: center;
      gap: var(--a2ui-space-2);
      font-size: var(--a2ui-text-xs);
      color: var(--a2ui-text-tertiary);
      animation: stepIn 0.25s ease forwards;
      opacity: 0;
    }

    @keyframes stepIn {
      from { opacity: 0; transform: translateX(-4px); }
      to { opacity: 1; transform: translateX(0); }
    }

    .step-icon {
      width: 14px;
      height: 14px;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }

    .step-icon svg {
      width: 12px;
      height: 12px;
    }

    .check {
      color: var(--a2ui-success);
    }

    .step-spinner {
      width: 10px;
      height: 10px;
      border: 1.5px solid var(--a2ui-border-default);
      border-top-color: var(--a2ui-text-tertiary);
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }
  `;

  /**
   * Steps to display. Parent controls progression.
   * If empty, falls back to default timed progression.
   */
  @property({ type: Array }) steps: ThinkingStep[] = [];

  private renderStepIcon(done: boolean) {
    if (done) {
      return html`
        <span class="step-icon check">
          <svg viewBox="0 0 24 24" fill="currentColor">
            <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
          </svg>
        </span>
      `;
    }
    return html`<span class="step-icon"><span class="step-spinner"></span></span>`;
  }

  render() {
    return html`
      <div class="thinking">
        <div class="avatar">AI</div>
        <div class="content">
          <div class="header">
            <span class="spinner"></span>
            <span>Thinking...</span>
          </div>
          ${this.steps.length > 0 ? html`
            <div class="steps">
              ${this.steps.map(step => html`
                <div class="step">
                  ${this.renderStepIcon(step.done)}
                  <span>${step.label}</span>
                </div>
              `)}
            </div>
          ` : ''}
        </div>
      </div>
    `;
  }
}
