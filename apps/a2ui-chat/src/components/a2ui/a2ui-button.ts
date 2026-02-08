import { LitElement, html, css } from 'lit';
import { customElement, property } from 'lit/decorators.js';

@customElement('a2ui-button')
export class A2UIButton extends LitElement {
  static styles = css`
    :host {
      display: inline-block;
    }

    button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: var(--a2ui-space-2);
      padding: var(--a2ui-space-2) var(--a2ui-space-4);
      font-family: var(--a2ui-font-family);
      font-size: var(--a2ui-text-sm);
      font-weight: var(--a2ui-font-medium);
      border-radius: var(--a2ui-radius-lg);
      cursor: pointer;
      transition: background-color var(--a2ui-transition-fast), color var(--a2ui-transition-fast), transform var(--a2ui-transition-fast), box-shadow var(--a2ui-transition-fast);
      border: none;
      outline: none;
    }

    button:focus-visible {
      box-shadow: 0 0 0 2px var(--a2ui-accent-subtle);
    }

    button:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }

    /* Variants */
    .default {
      background: var(--a2ui-bg-tertiary);
      color: var(--a2ui-text-primary);
      border: 1px solid var(--a2ui-border-default);
    }

    .default:hover:not(:disabled) {
      background: var(--a2ui-bg-elevated);
    }

    .primary {
      background: var(--a2ui-accent);
      color: var(--a2ui-text-inverse);
    }

    .primary:hover:not(:disabled) {
      background: var(--a2ui-accent-hover);
    }

    .outlined {
      background: transparent;
      color: var(--a2ui-accent);
      border: 1px solid var(--a2ui-accent);
    }

    .outlined:hover:not(:disabled) {
      background: var(--a2ui-accent-subtle);
    }

    .text {
      background: transparent;
      color: var(--a2ui-accent);
      padding: var(--a2ui-space-1) var(--a2ui-space-2);
    }

    .text:hover:not(:disabled) {
      background: var(--a2ui-accent-subtle);
    }

    .danger {
      background: var(--a2ui-error);
      color: white;
    }

    .danger:hover:not(:disabled) {
      filter: brightness(1.1);
    }

    /* Sizes */
    .sm {
      padding: var(--a2ui-space-1) var(--a2ui-space-3);
      font-size: var(--a2ui-text-xs);
    }

    .lg {
      padding: var(--a2ui-space-3) var(--a2ui-space-6);
      font-size: var(--a2ui-text-md);
    }
  `;

  @property({ type: String }) label = '';
  @property({ type: String }) variant: 'default' | 'primary' | 'outlined' | 'text' | 'danger' = 'default';
  @property({ type: String }) size: 'sm' | 'md' | 'lg' = 'md';
  @property({ type: Boolean }) disabled = false;

  private handleClick() {
    if (!this.disabled) {
      this.dispatchEvent(new CustomEvent('button-click', {
        detail: { label: this.label },
        bubbles: true,
        composed: true,
      }));
    }
  }

  render() {
    const sizeClass = this.size !== 'md' ? this.size : '';

    return html`
      <button 
        class="${this.variant} ${sizeClass}"
        ?disabled=${this.disabled}
        @click=${this.handleClick}
      >
        ${this.label || html`<slot></slot>`}
      </button>
    `;
  }
}
