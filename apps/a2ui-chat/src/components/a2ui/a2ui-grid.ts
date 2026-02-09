import { LitElement, html, css } from 'lit';
import { customElement, property } from 'lit/decorators.js';

/**
 * A2UI Grid — CSS class-based grid layout.
 *
 * Usage (declarative):
 *   <a2ui-grid columns="3" spacing="lg">
 *     <a2ui-card>...</a2ui-card>
 *     <a2ui-card>...</a2ui-card>
 *     <a2ui-card>...</a2ui-card>
 *   </a2ui-grid>
 *
 * CSS classes generated:
 *   .grid          — always present
 *   .cols-{1–6}    — column count
 *   .spacing-{size} — gap between items
 *
 * Responsive: collapses to single column below 600px.
 */
@customElement('a2ui-grid')
export class A2UIGrid extends LitElement {
  static styles = css`
    :host {
      display: block;
    }

    /* ── Base ─────────────────────────────── */
    .grid {
      display: grid;
    }

    /* ── Column classes ───────────────────── */
    .cols-1 { grid-template-columns: 1fr; }
    .cols-2 { grid-template-columns: repeat(2, 1fr); }
    .cols-3 { grid-template-columns: repeat(3, 1fr); }
    .cols-4 { grid-template-columns: repeat(4, 1fr); }
    .cols-5 { grid-template-columns: repeat(5, 1fr); }
    .cols-6 { grid-template-columns: repeat(6, 1fr); }

    /* ── Spacing (gap) classes ────────────── */
    .spacing-none { gap: 0; }
    .spacing-xs   { gap: 4px; }
    .spacing-sm   { gap: 8px; }
    .spacing-md   { gap: 16px; }
    .spacing-lg   { gap: 24px; }
    .spacing-xl   { gap: 32px; }

    /* ── Slotted children ────────────────── */
    ::slotted(*) {
      min-width: 0;
    }

    /* ── Responsive: stack on mobile ─────── */
    @media (max-width: 600px) {
      .cols-2, .cols-3, .cols-4, .cols-5, .cols-6 {
        grid-template-columns: 1fr;
      }
    }
  `;

  @property({ type: Number }) columns = 2;
  @property({ type: String }) spacing: 'none' | 'xs' | 'sm' | 'md' | 'lg' | 'xl' = 'lg';

  render() {
    const cols = Math.min(Math.max(this.columns, 1), 6);
    return html`
      <div class="grid cols-${cols} spacing-${this.spacing}">
        <slot></slot>
      </div>
    `;
  }
}
