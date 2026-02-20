import { LitElement, html, css, nothing } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import type { LoadingDisplay } from '../../config/ui-config';

export interface ThinkingStep {
  label: string;
  done: boolean;
  detail?: string;
  /** Backend tool identifier (e.g. "analyzer", "search", "llm"). */
  tool?: string;
}

/** Maps backend step IDs to loading display visibility. */
const STEP_VISIBILITY: Record<string, LoadingDisplay[]> = {
  tools:    ['comprehensive'],
  analyzer: ['comprehensive', 'moderate'],
  search:   ['comprehensive', 'moderate'],
  location: ['comprehensive', 'moderate'],
  llm:      ['comprehensive', 'moderate'],
};

function isStepVisible(toolId: string | undefined, level: LoadingDisplay): boolean {
  if (!toolId) return level !== 'basic';
  const allowed = STEP_VISIBILITY[toolId];
  return allowed ? allowed.includes(level) : level !== 'basic';
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

    .elapsed {
      color: var(--a2ui-text-tertiary);
      font-size: var(--a2ui-text-xs);
      margin-left: auto;
      font-variant-numeric: tabular-nums;
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

    /* ── Steps viewport (slot machine / rolodex) ─────── */

    .steps-viewport {
      overflow: hidden;
      position: relative;
      max-height: 140px;
      mask-image: linear-gradient(
        to bottom,
        black 0%,
        black 80%,
        transparent 100%
      );
      -webkit-mask-image: linear-gradient(
        to bottom,
        black 0%,
        black 80%,
        transparent 100%
      );
    }

    .steps {
      display: flex;
      flex-direction: column;
      gap: 2px;
      padding-left: var(--a2ui-space-1);
    }

    /* ── Individual step ────────────────────────────── */

    .step {
      display: flex;
      align-items: flex-start;
      gap: var(--a2ui-space-2);
      font-size: var(--a2ui-text-xs);
      padding: 3px 0;
      transition:
        opacity 0.35s cubic-bezier(0.22, 1, 0.36, 1),
        transform 0.35s cubic-bezier(0.22, 1, 0.36, 1),
        color 0.3s ease;
    }

    .step.active {
      opacity: 1;
      color: var(--a2ui-text-secondary);
    }

    .step.done {
      opacity: 0.45;
      color: var(--a2ui-text-tertiary);
      transform: translateY(-1px);
    }

    /* Entrance: slide up from below */
    .step.entering {
      animation: stepSlideUp 0.4s cubic-bezier(0.22, 1, 0.36, 1) forwards;
    }

    @keyframes stepSlideUp {
      from {
        opacity: 0;
        transform: translateY(16px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }

    .step-icon {
      width: 14px;
      height: 14px;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      margin-top: 1px;
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

    .step-text {
      display: flex;
      flex-direction: column;
      gap: 1px;
    }

    .step-detail {
      color: var(--a2ui-accent);
      font-size: 10px;
      font-style: italic;
      opacity: 0.85;
    }
  `;

  @property({ type: Array }) steps: ThinkingStep[] = [];
  @property({ type: String }) displayLevel: LoadingDisplay = 'moderate';

  @state() private elapsed = 0;
  @state() private enteredIds = new Set<string>();
  private timer = 0;

  connectedCallback() {
    super.connectedCallback();
    this.elapsed = 0;
    this.enteredIds = new Set();
    this.timer = window.setInterval(() => { this.elapsed++; }, 1000);
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    clearInterval(this.timer);
  }

  updated(changed: Map<string, unknown>) {
    if (changed.has('steps')) {
      for (const step of this.steps) {
        const key = step.tool || step.label;
        if (!this.enteredIds.has(key)) {
          this.enteredIds = new Set([...this.enteredIds, key]);
        }
      }
      // Auto-scroll to bottom of viewport
      const viewport = this.renderRoot.querySelector('.steps-viewport');
      if (viewport) {
        requestAnimationFrame(() => {
          viewport.scrollTop = viewport.scrollHeight;
        });
      }
    }
  }

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
    const visibleSteps = this.displayLevel === 'basic'
      ? []
      : this.steps.filter(s => isStepVisible(s.tool, this.displayLevel));

    const showDetail = this.displayLevel === 'comprehensive';

    return html`
      <div class="thinking">
        <div class="avatar">AI</div>
        <div class="content">
          <div class="header">
            <span class="spinner"></span>
            <span>Thinking...</span>
            ${this.elapsed >= 2 ? html`<span class="elapsed">${this.elapsed}s</span>` : nothing}
          </div>
          ${visibleSteps.length > 0 ? html`
            <div class="steps-viewport">
              <div class="steps">
                ${visibleSteps.map(step => {
                  const key = step.tool || step.label;
                  const isNew = this.enteredIds.has(key);
                  return html`
                    <div class="step ${step.done ? 'done' : 'active'} ${isNew ? 'entering' : ''}">
                      ${this.renderStepIcon(step.done)}
                      <span class="step-text">
                        <span>${step.label}</span>
                        ${showDetail && step.detail ? html`<span class="step-detail">${step.detail}</span>` : nothing}
                      </span>
                    </div>
                  `;
                })}
              </div>
            </div>
          ` : nothing}
        </div>
      </div>
    `;
  }
}
