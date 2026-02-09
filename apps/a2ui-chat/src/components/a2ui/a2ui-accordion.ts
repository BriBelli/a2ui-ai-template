import { LitElement, html, css, nothing } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';

export interface AccordionItem {
  id: string;
  title: string;
  content: string;
}

/**
 * A2UI Accordion — Expandable content sections (Molecular component).
 *
 * Composed of atoms: text (title, content) + icon (chevron).
 *
 * Usage:
 *   <a2ui-accordion
 *     .items=${[{ id: '1', title: 'Question?', content: 'Answer.' }]}
 *   ></a2ui-accordion>
 */
@customElement('a2ui-accordion')
export class A2UIAccordion extends LitElement {
  static styles = css`
    :host {
      display: block;
      width: 100%;
    }

    .accordion {
      display: flex;
      flex-direction: column;
    }

    .accordion-item {
      border-bottom: 1px solid var(--a2ui-border-default);
    }

    .accordion-item:last-child {
      border-bottom: none;
    }

    /* ── Trigger ────────────────────────── */
    .accordion-trigger {
      display: flex;
      align-items: center;
      justify-content: space-between;
      width: 100%;
      padding: var(--a2ui-space-4) 0;
      background: none;
      border: none;
      cursor: pointer;
      text-align: left;
      font-family: inherit;
      font-size: var(--a2ui-text-sm);
      font-weight: var(--a2ui-font-medium);
      color: var(--a2ui-text-primary);
      transition: color var(--a2ui-transition-fast);
    }

    .accordion-trigger:hover {
      color: var(--a2ui-accent);
    }

    .chevron {
      width: 16px;
      height: 16px;
      color: var(--a2ui-text-tertiary);
      flex-shrink: 0;
      transition: transform 0.2s ease;
    }

    .accordion-item.open .chevron {
      transform: rotate(180deg);
    }

    /* ── Panel ──────────────────────────── */
    .accordion-panel {
      overflow: hidden;
      max-height: 0;
      transition: max-height 0.25s ease;
    }

    .accordion-item.open .accordion-panel {
      max-height: 500px;
    }

    .accordion-content {
      padding: 0 0 var(--a2ui-space-4) 0;
      font-size: var(--a2ui-text-sm);
      color: var(--a2ui-text-secondary);
      line-height: 1.6;
    }
  `;

  @property({ type: Array }) items: AccordionItem[] = [];
  @property({ type: Boolean }) multiple = false;
  @state() private openIds: Set<string> = new Set();

  private toggle(id: string) {
    const next = new Set(this.openIds);
    if (next.has(id)) {
      next.delete(id);
    } else {
      if (!this.multiple) next.clear();
      next.add(id);
    }
    this.openIds = next;
  }

  render() {
    if (!this.items?.length) return nothing;

    return html`
      <div class="accordion">
        ${this.items.map(item => html`
          <div class="accordion-item ${this.openIds.has(item.id) ? 'open' : ''}">
            <button class="accordion-trigger" @click="${() => this.toggle(item.id)}" aria-expanded="${this.openIds.has(item.id)}">
              <span>${item.title}</span>
              <svg class="chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M6 9l6 6 6-6"/>
              </svg>
            </button>
            <div class="accordion-panel">
              <div class="accordion-content">${item.content}</div>
            </div>
          </div>
        `)}
      </div>
    `;
  }
}
