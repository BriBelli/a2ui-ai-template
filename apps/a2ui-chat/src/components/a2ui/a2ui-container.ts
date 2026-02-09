import { LitElement, html, css } from 'lit';
import { customElement, property } from 'lit/decorators.js';

/**
 * A2UI Container — CSS class-based flexbox layout.
 *
 * Usage (declarative):
 *   <a2ui-container layout="horizontal" spacing="md">
 *     <a2ui-chip>Tag 1</a2ui-chip>
 *     <a2ui-chip>Tag 2</a2ui-chip>
 *   </a2ui-container>
 *
 * CSS classes generated:
 *   .container      — always present (display: flex)
 *   .vertical/.horizontal — direction
 *   .spacing-{size} — gap between items
 *   .wrap           — flex-wrap: wrap
 *   .align-{value}  — align-items
 *   .justify-{value} — justify-content
 */
@customElement('a2ui-container')
export class A2UIContainer extends LitElement {
  static styles = css`
    :host {
      display: block;
    }

    /* ── Base ─────────────────────────────── */
    .container {
      display: flex;
    }

    /* ── Direction ────────────────────────── */
    .vertical   { flex-direction: column; }
    .horizontal { flex-direction: row; }

    /* ── Wrap ─────────────────────────────── */
    .wrap { flex-wrap: wrap; }

    /* ── Spacing (gap) classes ────────────── */
    .spacing-none { gap: 0; }
    .spacing-xs   { gap: 4px; }
    .spacing-sm   { gap: 8px; }
    .spacing-md   { gap: 16px; }
    .spacing-lg   { gap: 24px; }
    .spacing-xl   { gap: 32px; }

    /* ── Alignment ────────────────────────── */
    .align-start   { align-items: flex-start; }
    .align-center  { align-items: center; }
    .align-end     { align-items: flex-end; }
    .align-stretch { align-items: stretch; }

    /* ── Justification ────────────────────── */
    .justify-start   { justify-content: flex-start; }
    .justify-center  { justify-content: center; }
    .justify-end     { justify-content: flex-end; }
    .justify-between { justify-content: space-between; }
    .justify-around  { justify-content: space-around; }
  `;

  @property({ type: String }) layout: 'vertical' | 'horizontal' = 'vertical';
  @property({ type: String }) spacing: 'none' | 'xs' | 'sm' | 'md' | 'lg' | 'xl' = 'md';
  @property({ type: Boolean }) wrap = false;
  @property({ type: String }) align: 'start' | 'center' | 'end' | 'stretch' = 'stretch';
  @property({ type: String }) justify: 'start' | 'center' | 'end' | 'between' | 'around' = 'start';

  render() {
    const classes = [
      'container',
      this.layout,
      `spacing-${this.spacing}`,
      `align-${this.align}`,
      `justify-${this.justify}`,
      this.wrap ? 'wrap' : '',
    ].filter(Boolean).join(' ');

    return html`
      <div class=${classes}>
        <slot></slot>
      </div>
    `;
  }
}
