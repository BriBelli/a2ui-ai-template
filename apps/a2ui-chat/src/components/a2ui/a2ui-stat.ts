import { LitElement, html, css, nothing, unsafeCSS } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { md, markdownStyles } from '../../services/markdown';

/**
 * A2UI Stat — KPI / metric display (Molecular component).
 *
 * Composed of atoms: text (label, value, description) + badge (trend).
 * Inspired by Shadcn dashboard stat cards.
 *
 * Usage:
 *   <a2ui-stat
 *     label="Total Revenue"
 *     value="$1,250.00"
 *     trend="+12.5%"
 *     trendDirection="up"
 *     description="Trending up this month"
 *   ></a2ui-stat>
 */
@customElement('a2ui-stat')
export class A2UIStat extends LitElement {
  static styles = css`
    :host {
      display: flex;
      flex-direction: column;
      flex: 1;
      min-width: 0;        /* allow shrinking in flex/grid parents */
      overflow: hidden;
    }

    .stat {
      flex: 1;
      background: var(--a2ui-bg-tertiary);
      border-radius: var(--a2ui-radius-lg);
      padding: var(--a2ui-space-5);
      display: flex;
      flex-direction: column;
      gap: 4px;
      min-width: 0;        /* allow shrinking inside flex/grid parents */
      overflow: hidden;    /* clip any overflowing content */
    }

    /* ── Header: label + trend badge ───── */
    .stat-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: var(--a2ui-space-2);
    }

    .stat-label {
      font-size: var(--a2ui-text-sm);
      font-weight: var(--a2ui-font-medium);
      color: var(--a2ui-text-secondary);
      margin: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .stat-trend {
      display: inline-flex;
      align-items: center;
      gap: 2px;
      font-size: 11px;
      font-weight: var(--a2ui-font-medium);
      padding: 2px 8px;
      border-radius: var(--a2ui-radius-full);
    }

    .stat-trend.up {
      color: var(--a2ui-success);
      background: rgba(52, 168, 83, 0.12);
    }

    .stat-trend.down {
      color: var(--a2ui-error);
      background: rgba(234, 67, 53, 0.12);
    }

    .stat-trend.neutral {
      color: var(--a2ui-text-tertiary);
      background: var(--a2ui-bg-elevated);
    }

    .trend-icon {
      width: 12px;
      height: 12px;
    }

    /* ── Value ──────────────────────────── */
    .stat-value {
      font-size: var(--a2ui-text-2xl, 1.5rem);
      font-weight: var(--a2ui-font-bold);
      color: var(--a2ui-text-primary);
      line-height: 1.2;
      margin: var(--a2ui-space-1) 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    /* ── Description ───────────────────── */
    .stat-description {
      font-size: var(--a2ui-text-xs);
      color: var(--a2ui-text-tertiary);
      margin: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    ${unsafeCSS(markdownStyles)}
  `;

  @property({ type: String }) label = '';
  @property({ type: String }) value = '';
  @property({ type: String }) trend = '';
  @property({ type: String }) trendDirection: 'up' | 'down' | 'neutral' =
    'neutral';
  @property({ type: String }) description = '';

  private renderTrendIcon() {
    if (this.trendDirection === 'up') {
      return html`<svg class="trend-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M7 17l5-5 5 5"/><path d="M7 7h10"/></svg>`;
    }
    if (this.trendDirection === 'down') {
      return html`<svg class="trend-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M7 7l5 5 5-5"/><path d="M7 17h10"/></svg>`;
    }
    return nothing;
  }

  render() {
    // Auto-detect trend direction from the trend string
    let dir = this.trendDirection;
    if (this.trend && dir === 'neutral') {
      if (this.trend.startsWith('+') || this.trend.toLowerCase().includes('up'))
        dir = 'up';
      else if (
        this.trend.startsWith('-') ||
        this.trend.toLowerCase().includes('down')
      )
        dir = 'down';
    }

    return html`
      <div class="stat">
        <div class="stat-header">
          <p class="stat-label">${this.label}</p>
          ${
            this.trend
              ? html`
            <span class="stat-trend ${dir}">
              ${this.renderTrendIcon()}
              ${this.trend}
            </span>
          `
              : nothing
          }
        </div>
        <div class="stat-value">${this.value}</div>
        ${
          this.description
            ? html`
          <p class="stat-description">${md(this.description)}</p>
        `
            : nothing
        }
      </div>
    `;
  }
}
