import { LitElement, html, css } from 'lit';
import { customElement, property } from 'lit/decorators.js';

@customElement('a2ui-card')
export class A2UICard extends LitElement {
  static styles = css`
    :host {
      display: flex;
      flex-direction: column;
      flex: 1;
    }

    .card {
      flex: 1;
      background: var(--a2ui-bg-tertiary);
      border-radius: var(--a2ui-radius-lg);
      padding: var(--a2ui-space-5);
      transition: border-color var(--a2ui-transition-fast), box-shadow var(--a2ui-transition-fast);
    }

    .card:hover {
      border-color: var(--a2ui-border-default);
      box-shadow: var(--a2ui-shadow-sm);
    }

    .card-header {
      margin-bottom: var(--a2ui-space-3);
    }

    .card-title {
      font-size: var(--a2ui-text-lg);
      font-weight: var(--a2ui-font-medium);
      color: var(--a2ui-text-primary);
      margin: 0;
    }

    .card-subtitle {
      font-size: var(--a2ui-text-sm);
      color: var(--a2ui-text-secondary);
      margin: var(--a2ui-space-1) 0 0 0;
    }

    .card-content {
      display: flex;
      flex-direction: column;
      gap: 16px;
      color: var(--a2ui-text-primary);
    }

    .card-footer {
      margin-top: var(--a2ui-space-4);
      padding-top: var(--a2ui-space-3);
      border-top: 1px solid var(--a2ui-border-subtle);
    }
  `;

  @property({ type: String }) cardTitle = '';
  @property({ type: String }) subtitle = '';

  render() {
    return html`
      <div class="card">
        ${(this.cardTitle || this.subtitle) ? html`
          <div class="card-header">
            ${this.cardTitle ? html`<h3 class="card-title">${this.cardTitle}</h3>` : ''}
            ${this.subtitle ? html`<p class="card-subtitle">${this.subtitle}</p>` : ''}
          </div>
        ` : ''}
        <div class="card-content">
          <slot></slot>
        </div>
      </div>
    `;
  }
}
