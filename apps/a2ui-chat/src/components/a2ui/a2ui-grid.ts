import { LitElement, html, css } from 'lit';
import { customElement, property } from 'lit/decorators.js';

/**
 * A2UI Grid — Flexbox-based responsive grid with wrapping.
 *
 * Two modes:
 *
 * 1. **Fixed columns** (`columns="5"`) — targets N items per row.
 *    Items wrap to the next row when the container is too narrow
 *    to fit all N at `minItemWidth`.
 *
 * 2. **Auto-fit** (`columns="auto"`) — items flow at `minItemWidth`,
 *    growing to fill available space. The browser decides column count.
 *
 * Usage:
 *   <!-- Fixed 5 columns, wraps when items can't fit at 150px -->
 *   <a2ui-grid columns="5" spacing="lg" minItemWidth="150px">...</a2ui-grid>
 *
 *   <!-- Auto-fit: items wrap dynamically -->
 *   <a2ui-grid columns="auto" spacing="md" minItemWidth="200px">...</a2ui-grid>
 */
@customElement('a2ui-grid')
export class A2UIGrid extends LitElement {
  static styles = css`
    :host {
      display: block;
      width: 100%;
    }

    /* ── Base: flex container with wrap ───── */
    .grid {
      display: flex;
      flex-wrap: wrap;
      width: 100%;
    }

    /* ── Spacing (gap) classes ────────────── */
    .spacing-none { gap: 0; }
    .spacing-xs   { gap: 4px; }
    .spacing-sm   { gap: 8px; }
    .spacing-md   { gap: 16px; }
    .spacing-lg   { gap: 20px; }
    .spacing-xl   { gap: 32px; }

    /* ── Fixed-column mode ───────────────── */
    /* Each item targets 100%/N minus gap share.         */
    /* Items shrink down to min-width, then wrap.        */
    .mode-fixed ::slotted(*) {
      flex: 0 1 calc(
        (100% - (var(--grid-columns, 2) - 1) * var(--grid-gap, 20px))
        / var(--grid-columns, 2)
      );
      min-width: var(--grid-min-width, 150px);
      box-sizing: border-box;
    }

    /* ── Auto mode ───────────────────────── */
    /* Items grow from min-width to fill available space. */
    .mode-auto ::slotted(*) {
      flex: 1 1 var(--grid-min-width, 180px);
      min-width: var(--grid-min-width, 180px);
      box-sizing: border-box;
    }
  `;

  /** Number of columns (1–12) or "auto" for auto-fit wrapping. */
  @property({ type: String }) columns: string | number = '2';

  /** Gap between grid items. */
  @property({ type: String }) spacing:
    | 'none'
    | 'xs'
    | 'sm'
    | 'md'
    | 'lg'
    | 'xl' = 'lg';

  /** Minimum item width — items wrap when they'd shrink below this. */
  @property({ type: String }) minItemWidth = '150px';

  render() {
    const raw = String(this.columns).trim().toLowerCase();
    const isAuto = raw === 'auto';
    const cols = isAuto ? 0 : Math.min(Math.max(Number(raw) || 2, 1), 12);

    const gapMap: Record<string, number> = {
      none: 0,
      xs: 4,
      sm: 8,
      md: 16,
      lg: 20,
      xl: 32,
    };
    const gapPx = gapMap[this.spacing] ?? 20;

    const style = isAuto
      ? `--grid-min-width: ${this.minItemWidth}`
      : `--grid-columns: ${cols}; --grid-gap: ${gapPx}px; --grid-min-width: ${this.minItemWidth}`;

    return html`
      <div
        class="grid ${isAuto ? 'mode-auto' : 'mode-fixed'} spacing-${
      this.spacing
    }"
        style="${style}"
      >
        <slot></slot>
      </div>
    `;
  }
}
