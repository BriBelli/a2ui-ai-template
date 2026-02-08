import { LitElement, html, css } from 'lit';
import { customElement, property } from 'lit/decorators.js';

/**
 * A2UI Grid — simple CSS Grid layout.
 *
 * columns = the actual number of columns you want.
 *   grid(columns: 4) → 4 equal columns
 *   grid(columns: 2) → 2 equal columns
 *
 * Children fill one column each by default.
 */
@customElement('a2ui-grid')
export class A2UIGrid extends LitElement {
  static styles = css`
    :host {
      display: block;
    }

    .grid {
      display: grid;
      grid-template-columns: repeat(var(--cols, 2), 1fr);
    }

    .gap-none { gap: 0; }
    .gap-xs   { gap: var(--a2ui-space-1); }
    .gap-sm   { gap: var(--a2ui-space-2); }
    .gap-md   { gap: var(--a2ui-space-4); }
    .gap-lg   { gap: var(--a2ui-space-6); }
    .gap-xl   { gap: var(--a2ui-space-8); }

    ::slotted(*) {
      min-width: 0;
    }

    @media (max-width: 600px) {
      .grid {
        grid-template-columns: 1fr;
      }
    }
  `;

  @property({ type: Number }) columns = 2;
  @property({ type: String }) gap: 'none' | 'xs' | 'sm' | 'md' | 'lg' | 'xl' = 'md';

  render() {
    return html`
      <div class="grid gap-${this.gap}" style="--cols: ${this.columns}">
        <slot></slot>
      </div>
    `;
  }
}
