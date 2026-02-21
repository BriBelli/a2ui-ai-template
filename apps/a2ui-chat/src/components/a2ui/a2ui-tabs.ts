import { LitElement, html, css, nothing, unsafeCSS } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { md, markdownStyles } from '../../services/markdown';

export interface TabItem {
  id: string;
  label: string;
  count?: number;
  content: string;
}

/**
 * A2UI Tabs — Tabbed content panels (Molecular component).
 *
 * Composed of atoms: text (label, badge, content).
 * Inspired by Shadcn tabs component.
 *
 * Usage:
 *   <a2ui-tabs
 *     .tabs=${[{ id: '1', label: 'Overview', content: 'Overview text...' }]}
 *   ></a2ui-tabs>
 */
@customElement('a2ui-tabs')
export class A2UITabs extends LitElement {
  static styles = css`
    :host {
      display: block;
      width: 100%;
    }

    /* ── Tab list ───────────────────────── */
    .tab-list {
      display: flex;
      gap: 2px;
      border-bottom: 1px solid var(--a2ui-border-default);
      overflow-x: auto;
      -webkit-overflow-scrolling: touch;
      scrollbar-width: none;
    }

    .tab-list::-webkit-scrollbar { display: none; }

    /* ── Tab trigger ────────────────────── */
    .tab-trigger {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: var(--a2ui-space-2) var(--a2ui-space-4);
      background: none;
      border: none;
      border-bottom: 2px solid transparent;
      cursor: pointer;
      font-family: inherit;
      font-size: var(--a2ui-text-sm);
      font-weight: var(--a2ui-font-medium);
      color: var(--a2ui-text-tertiary);
      white-space: nowrap;
      transition: color var(--a2ui-transition-fast), border-color var(--a2ui-transition-fast);
    }

    .tab-trigger:hover {
      color: var(--a2ui-text-primary);
    }

    .tab-trigger.active {
      color: var(--a2ui-text-primary);
      border-bottom-color: var(--a2ui-accent);
    }

    .tab-count {
      font-size: 10px;
      min-width: 16px;
      height: 16px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 0 4px;
      border-radius: var(--a2ui-radius-full);
      background: var(--a2ui-bg-elevated);
      color: var(--a2ui-text-tertiary);
    }

    .tab-trigger.active .tab-count {
      background: var(--a2ui-accent);
      color: var(--a2ui-bg-primary);
    }

    /* ── Tab panel ──────────────────────── */
    .tab-panel {
      padding: var(--a2ui-space-4) 0;
      font-size: var(--a2ui-text-sm);
      color: var(--a2ui-text-secondary);
      line-height: 1.6;
    }

    ${unsafeCSS(markdownStyles)}
  `;

  @property({ type: Array }) tabs: TabItem[] = [];
  @state() private activeId = '';

  updated(changed: Map<string, unknown>) {
    if (changed.has('tabs') && this.tabs?.length && !this.activeId) {
      this.activeId = this.tabs[0].id;
    }
  }

  render() {
    if (!this.tabs?.length) return nothing;

    const active = this.tabs.find(t => t.id === this.activeId) ?? this.tabs[0];

    return html`
      <div role="tablist" class="tab-list">
        ${this.tabs.map(tab => html`
          <button
            role="tab"
            class="tab-trigger ${tab.id === active.id ? 'active' : ''}"
            aria-selected="${tab.id === active.id}"
            @click="${() => { this.activeId = tab.id; }}"
          >
            ${tab.label}
            ${tab.count != null ? html`<span class="tab-count">${tab.count}</span>` : nothing}
          </button>
        `)}
      </div>
      <div role="tabpanel" class="tab-panel">
        ${md(active.content)}
      </div>
    `;
  }
}
