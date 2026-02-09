import { LitElement, html, css, nothing } from 'lit';
import { customElement, property } from 'lit/decorators.js';

/**
 * A2UI Progress — Progress/gauge bar (Atomic component).
 *
 * Renders a labelled progress bar, useful for stats, ratings, completion.
 *
 * Usage:
 *   <a2ui-progress label="Battery" value="72" max="100" variant="success"></a2ui-progress>
 */
@customElement('a2ui-progress')
export class A2UIProgress extends LitElement {
  static styles = css`
    :host {
      display: block;
      width: 100%;
    }

    .progress {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }

    .progress-meta {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
    }

    .progress-label {
      font-size: var(--a2ui-text-sm);
      color: var(--a2ui-text-secondary);
      font-weight: var(--a2ui-font-medium);
    }

    .progress-value {
      font-size: var(--a2ui-text-sm);
      color: var(--a2ui-text-tertiary);
      font-variant-numeric: tabular-nums;
    }

    /* ── Track ──────────────────────────── */
    .progress-track {
      width: 100%;
      height: 8px;
      background: var(--a2ui-bg-elevated);
      border-radius: var(--a2ui-radius-full);
      overflow: hidden;
    }

    :host([size="sm"]) .progress-track { height: 4px; }
    :host([size="lg"]) .progress-track { height: 12px; }

    /* ── Fill ───────────────────────────── */
    .progress-fill {
      height: 100%;
      border-radius: var(--a2ui-radius-full);
      transition: width 0.6s cubic-bezier(0.22, 1, 0.36, 1);
    }

    .fill-default { background: var(--a2ui-accent); }
    .fill-success { background: var(--a2ui-success); }
    .fill-warning { background: var(--a2ui-warning); }
    .fill-error   { background: var(--a2ui-error); }
  `;

  @property({ type: String })  label = '';
  @property({ type: Number })  value = 0;
  @property({ type: Number })  max = 100;
  @property({ type: String })  variant: 'default' | 'success' | 'warning' | 'error' = 'default';
  @property({ type: String })  size: 'sm' | 'md' | 'lg' = 'md';
  @property({ type: Boolean }) showValue = true;

  render() {
    const pct = Math.min(100, Math.max(0, (this.value / this.max) * 100));

    return html`
      <div class="progress" role="progressbar"
           aria-valuenow="${this.value}"
           aria-valuemin="0"
           aria-valuemax="${this.max}"
           aria-label="${this.label || 'Progress'}">
        ${(this.label || this.showValue) ? html`
          <div class="progress-meta">
            ${this.label ? html`<span class="progress-label">${this.label}</span>` : nothing}
            ${this.showValue ? html`<span class="progress-value">${this.value}${this.max === 100 ? '%' : ` / ${this.max}`}</span>` : nothing}
          </div>
        ` : nothing}
        <div class="progress-track">
          <div class="progress-fill fill-${this.variant}" style="width: ${pct}%"></div>
        </div>
      </div>
    `;
  }
}
