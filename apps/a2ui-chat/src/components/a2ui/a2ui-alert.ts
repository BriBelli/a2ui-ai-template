import { LitElement, html, css, nothing } from 'lit';
import { customElement, property } from 'lit/decorators.js';

/**
 * A2UI Alert — Status banner (Molecular component).
 *
 * Composed of atoms: icon + text (title, description).
 *
 * Usage:
 *   <a2ui-alert
 *     variant="warning"
 *     alertTitle="Market Closed"
 *     description="Data is delayed by 15 minutes."
 *   ></a2ui-alert>
 */
@customElement('a2ui-alert')
export class A2UIAlert extends LitElement {
  static styles = css`
    :host {
      display: block;
      width: 100%;
    }

    .alert {
      display: flex;
      gap: var(--a2ui-space-3);
      padding: var(--a2ui-space-3) var(--a2ui-space-4);
      border-radius: var(--a2ui-radius-md);
      border: 1px solid var(--a2ui-border-default);
    }

    /* ── Variants ───────────────────────── */
    .alert.info {
      background: rgba(66, 133, 244, 0.08);
      border-color: rgba(66, 133, 244, 0.2);
    }
    .alert.info .alert-icon { color: var(--a2ui-accent); }

    .alert.success {
      background: rgba(52, 168, 83, 0.08);
      border-color: rgba(52, 168, 83, 0.2);
    }
    .alert.success .alert-icon { color: var(--a2ui-success); }

    .alert.warning {
      background: rgba(251, 188, 4, 0.08);
      border-color: rgba(251, 188, 4, 0.2);
    }
    .alert.warning .alert-icon { color: var(--a2ui-warning); }

    .alert.error {
      background: rgba(234, 67, 53, 0.08);
      border-color: rgba(234, 67, 53, 0.2);
    }
    .alert.error .alert-icon { color: var(--a2ui-error); }

    .alert.default {
      background: var(--a2ui-bg-tertiary);
    }
    .alert.default .alert-icon { color: var(--a2ui-text-secondary); }

    /* ── Icon ───────────────────────────── */
    .alert-icon {
      flex-shrink: 0;
      width: 18px;
      height: 18px;
      margin-top: 1px;
    }

    /* ── Body ───────────────────────────── */
    .alert-body {
      flex: 1;
      display: flex;
      flex-direction: column;
      gap: 2px;
    }

    .alert-title {
      font-size: var(--a2ui-text-sm);
      font-weight: var(--a2ui-font-semibold);
      color: var(--a2ui-text-primary);
      margin: 0;
    }

    .alert-description {
      font-size: var(--a2ui-text-sm);
      color: var(--a2ui-text-secondary);
      margin: 0;
      line-height: 1.5;
    }
  `;

  @property({ type: String }) variant: 'default' | 'info' | 'success' | 'warning' | 'error' = 'default';
  @property({ type: String }) alertTitle = '';
  @property({ type: String }) description = '';

  private renderIcon() {
    const icons: Record<string, unknown> = {
      info: html`<svg class="alert-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`,
      success: html`<svg class="alert-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>`,
      warning: html`<svg class="alert-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`,
      error: html`<svg class="alert-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>`,
      default: html`<svg class="alert-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`,
    };
    return icons[this.variant] ?? icons.default;
  }

  render() {
    return html`
      <div class="alert ${this.variant}">
        ${this.renderIcon()}
        <div class="alert-body">
          ${this.alertTitle ? html`<p class="alert-title">${this.alertTitle}</p>` : nothing}
          ${this.description ? html`<p class="alert-description">${this.description}</p>` : nothing}
        </div>
      </div>
    `;
  }
}
