import { LitElement, html, css } from 'lit';
import { customElement, property } from 'lit/decorators.js';

/** A simple option: just a value/label pair. */
export interface SelectItem {
  value: string;
  label: string;
}

/** A group of options under a category header. */
export interface SelectGroup {
  label: string;
  items: SelectItem[];
}

@customElement('a2ui-model-selector')
export class A2UIModelSelector extends LitElement {
  static styles = css`
    :host {
      display: block;
    }

    .selector-container {
      display: flex;
      align-items: center;
      gap: var(--a2ui-space-2);
    }

    select {
      appearance: none;
      background: var(--a2ui-bg-secondary);
      border: 1px solid var(--a2ui-border-default);
      border-radius: var(--a2ui-radius-md);
      padding: var(--a2ui-space-1) var(--a2ui-space-8) var(--a2ui-space-1) var(--a2ui-space-3);
      font-family: var(--a2ui-font-family);
      font-size: var(--a2ui-text-sm);
      color: var(--a2ui-text-primary);
      cursor: pointer;
      transition: border-color var(--a2ui-transition-fast), box-shadow var(--a2ui-transition-fast);
      background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='%239aa0a6'%3E%3Cpath d='M7 10l5 5 5-5z'/%3E%3C/svg%3E");
      background-repeat: no-repeat;
      background-position: right 8px center;
      min-width: 180px;
    }

    select:hover {
      border-color: var(--a2ui-accent);
      background-color: var(--a2ui-bg-tertiary);
    }

    select:focus {
      outline: none;
      border-color: var(--a2ui-accent);
      box-shadow: 0 0 0 2px var(--a2ui-accent-subtle);
    }

    select optgroup {
      font-style: normal;
      font-weight: 600;
      color: var(--a2ui-text-secondary);
    }

    .status {
      display: flex;
      align-items: center;
      gap: var(--a2ui-space-1);
      font-size: var(--a2ui-text-xs);
      color: var(--a2ui-text-tertiary);
    }

    .status-dot {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: var(--a2ui-success);
    }

    .status-dot.offline {
      background: var(--a2ui-error);
    }

    .no-providers {
      font-size: var(--a2ui-text-sm);
      color: var(--a2ui-text-tertiary);
      padding: var(--a2ui-space-2);
    }

    /* ── Responsive: Tablet (≤768px) ──────────────────── */

    @media (max-width: 768px) {
      select {
        min-width: 140px;
        font-size: var(--a2ui-text-xs);
        padding: var(--a2ui-space-1) var(--a2ui-space-6) var(--a2ui-space-1) var(--a2ui-space-2);
      }

      .status {
        font-size: 10px;
      }
    }

    /* ── Responsive: Mobile (≤480px) ─────────────────── */

    @media (max-width: 480px) {
      .selector-container {
        gap: var(--a2ui-space-1);
      }

      select {
        min-width: 0;
        max-width: 130px;
        padding: 2px var(--a2ui-space-5) 2px var(--a2ui-space-2);
        font-size: 11px;
        background-position: right 4px center;
      }

      .status {
        display: none;
      }
    }
  `;

  // ── Flexible input ──────────────────────────────────────
  //
  // Flat list (the common case):
  //   .items=${['GPT-4.1', 'Claude 4']}          ← string[]
  //   .items=${[{value:'gpt4', label:'GPT-4.1'}]} ← SelectItem[]
  //
  // Grouped (multi-provider / categorised):
  //   .groups=${[{label:'OpenAI', items:[…]}, …]}  ← SelectGroup[]
  //
  // When both are set, groups wins.

  /** Flat list — accepts string[] or SelectItem[]. */
  @property({ type: Array }) items: (string | SelectItem)[] = [];

  /** Grouped list — renders <optgroup> categories. */
  @property({ type: Array }) groups: SelectGroup[] = [];

  /** Currently selected value. */
  @property({ type: String }) value = '';

  /** Whether to show the connection status indicator. */
  @property({ type: Boolean }) showStatus = false;

  /** Placeholder shown when no value is selected. */
  @property({ type: String }) placeholder = '';

  // ── Helpers ─────────────────────────────────────────────

  /** Normalise a mixed items array into SelectItem[]. */
  private normalizeItems(raw: (string | SelectItem)[]): SelectItem[] {
    return raw.map(item =>
      typeof item === 'string' ? { value: item, label: item } : item
    );
  }

  private handleChange(e: Event) {
    const newValue = (e.target as HTMLSelectElement).value;
    this.value = newValue;

    this.dispatchEvent(new CustomEvent('change', {
      detail: { value: newValue },
      bubbles: true,
      composed: true,
    }));
  }

  // ── Render ──────────────────────────────────────────────

  private renderOption(item: SelectItem) {
    return html`
      <option value=${item.value} ?selected=${item.value === this.value}>${item.label}</option>
    `;
  }

  render() {
    const hasGroups = this.groups.length > 0;
    const hasItems = this.items.length > 0;

    if (!hasGroups && !hasItems) {
      return html`
        <div class="no-providers">
          <span class="status">
            <span class="status-dot offline"></span>
            No options available
          </span>
        </div>
      `;
    }

    return html`
      <div class="selector-container">
        <select aria-label="Select option" @change=${this.handleChange}>
          ${this.placeholder ? html`
            <option value="" disabled ?selected=${!this.value}>${this.placeholder}</option>
          ` : ''}
          ${hasGroups
            ? (this.groups.length === 1
                ? this.groups[0].items.map(item => this.renderOption(item))
                : this.groups.map(group => html`
                    <optgroup label=${group.label}>
                      ${group.items.map(item => this.renderOption(item))}
                    </optgroup>
                  `))
            : this.normalizeItems(this.items).map(item => this.renderOption(item))
          }
        </select>

        ${this.showStatus ? html`
          <span class="status">
            <span class="status-dot"></span>
            Connected
          </span>
        ` : ''}
      </div>
    `;
  }
}
