import { LitElement, html, css } from 'lit';
import { customElement, property } from 'lit/decorators.js';

@customElement('a2ui-chip')
export class A2UIChip extends LitElement {
  static styles = css`
    :host {
      display: inline-block;
    }

    .chip {
      display: inline-flex;
      align-items: center;
      gap: var(--a2ui-space-1);
      padding: var(--a2ui-space-1) var(--a2ui-space-3);
      font-size: var(--a2ui-text-sm);
      font-weight: var(--a2ui-font-medium);
      border-radius: var(--a2ui-radius-full);
      transition: background-color var(--a2ui-transition-fast), color var(--a2ui-transition-fast);
    }

    .chip.clickable {
      cursor: pointer;
    }

    .chip.clickable:hover {
      filter: brightness(1.1);
    }

    /* Variants */
    .default {
      background: var(--a2ui-bg-tertiary);
      color: var(--a2ui-text-primary);
      border: 1px solid var(--a2ui-border-default);
    }

    .primary {
      background: var(--a2ui-accent-subtle);
      color: var(--a2ui-accent);
      border: 1px solid var(--a2ui-accent);
    }

    .success {
      background: var(--a2ui-success-bg);
      color: var(--a2ui-success);
      border: 1px solid transparent;
    }

    .warning {
      background: var(--a2ui-warning-bg);
      color: var(--a2ui-warning);
      border: 1px solid transparent;
    }

    .error {
      background: var(--a2ui-error-bg);
      color: var(--a2ui-error);
      border: 1px solid transparent;
    }

    .icon {
      width: 14px;
      height: 14px;
    }
  `;

  @property({ type: String }) label = '';
  @property({ type: String }) variant: 'default' | 'primary' | 'success' | 'warning' | 'error' = 'default';
  @property({ type: Boolean }) clickable = false;
  @property({ type: String }) icon = '';

  private handleClick() {
    if (this.clickable) {
      this.dispatchEvent(new CustomEvent('chip-click', {
        detail: { label: this.label },
        bubbles: true,
        composed: true,
      }));
    }
  }

  render() {
    return html`
      <span 
        class="chip ${this.variant} ${this.clickable ? 'clickable' : ''}"
        @click=${this.handleClick}
      >
        ${this.icon ? html`<span class="icon">${this.icon}</span>` : ''}
        ${this.label}
      </span>
    `;
  }
}
