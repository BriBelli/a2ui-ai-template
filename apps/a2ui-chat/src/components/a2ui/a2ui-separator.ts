import { LitElement, html, css } from 'lit';
import { customElement, property } from 'lit/decorators.js';

/**
 * A2UI Separator — Visual divider (Atomic component).
 *
 * Renders a horizontal or vertical line to separate content sections.
 *
 * Usage:
 *   <a2ui-separator></a2ui-separator>
 *   <a2ui-separator orientation="vertical"></a2ui-separator>
 *   <a2ui-separator label="OR"></a2ui-separator>
 */
@customElement('a2ui-separator')
export class A2UISeparator extends LitElement {
  static styles = css`
    :host {
      display: block;
    }

    :host([orientation="vertical"]) {
      display: inline-block;
      height: 100%;
    }

    .separator {
      display: flex;
      align-items: center;
      gap: var(--a2ui-space-3);
    }

    .separator.horizontal {
      width: 100%;
      margin: var(--a2ui-space-2) 0;
    }

    .separator.vertical {
      flex-direction: column;
      height: 100%;
      width: auto;
    }

    .line {
      flex: 1;
      background: var(--a2ui-border-default);
    }

    .horizontal .line {
      height: 1px;
      min-width: 16px;
    }

    .vertical .line {
      width: 1px;
      min-height: 16px;
    }

    .label {
      font-size: var(--a2ui-text-xs);
      color: var(--a2ui-text-tertiary);
      font-weight: var(--a2ui-font-medium);
      white-space: nowrap;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }
  `;

  @property({ type: String }) orientation: 'horizontal' | 'vertical' = 'horizontal';
  @property({ type: String }) label = '';

  render() {
    return html`
      <div class="separator ${this.orientation}" role="separator" aria-orientation="${this.orientation}">
        <div class="line"></div>
        ${this.label ? html`<span class="label">${this.label}</span><div class="line"></div>` : ''}
      </div>
    `;
  }
}
