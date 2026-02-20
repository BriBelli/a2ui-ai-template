import { LitElement, html, css, nothing, unsafeCSS } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { md, markdownStyles } from '../../services/markdown';

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

    ${unsafeCSS(markdownStyles)}
  `;

  @property({ type: String }) variant: 'default' | 'info' | 'success' | 'warning' | 'error' = 'default';
  @property({ type: String }) alertTitle = '';
  @property({ type: String }) description = '';

  private renderIcon() {
    const icons: Record<string, unknown> = {
      info: html`<svg class="alert-icon" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/></svg>`,
      success: html`<svg class="alert-icon" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>`,
      warning: html`<svg class="alert-icon" viewBox="0 0 24 24" fill="currentColor"><path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/></svg>`,
      error: html`<svg class="alert-icon" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>`,
      default: html`<svg class="alert-icon" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/></svg>`,
    };
    return icons[this.variant] ?? icons.default;
  }

  render() {
    return html`
      <div class="alert ${this.variant}">
        ${this.renderIcon()}
        <div class="alert-body">
          ${this.alertTitle ? html`<p class="alert-title">${this.alertTitle}</p>` : nothing}
          ${this.description ? html`<div class="alert-description">${md(this.description)}</div>` : nothing}
        </div>
      </div>
    `;
  }
}