import { LitElement, html, css } from 'lit';
import { customElement, property } from 'lit/decorators.js';

interface TableColumn {
  key: string;
  label: string;
  width?: string;
  align?: 'left' | 'center' | 'right';
}

@customElement('a2ui-data-table')
export class A2UIDataTable extends LitElement {
  static styles = css`
    :host {
      display: block;
      overflow-x: auto;
      background: var(--a2ui-bg-tertiary);
      border-radius: var(--a2ui-radius-lg);
      padding: var(--a2ui-space-2) var(--a2ui-space-3);
    }

    .table {
      width: 100%;
      border-collapse: collapse;
      font-size: var(--a2ui-text-sm);
    }

    .table th {
      text-align: left;
      padding: var(--a2ui-space-3) var(--a2ui-space-3);
      font-weight: var(--a2ui-font-medium);
      color: var(--a2ui-text-secondary);
      border-bottom: 1px solid var(--a2ui-border-default);
      white-space: nowrap;
    }

    .table td {
      padding: var(--a2ui-space-3) var(--a2ui-space-3);
      color: var(--a2ui-text-primary);
      border-bottom: 1px solid var(--a2ui-border-subtle);
    }

    .table tbody tr:hover {
      background: var(--a2ui-bg-hover);
    }

    .table tbody tr:last-child td {
      border-bottom: none;
    }

    .align-left { text-align: left; }
    .align-center { text-align: center; }
    .align-right { text-align: right; }

    .positive {
      color: var(--a2ui-success);
    }

    .negative {
      color: var(--a2ui-error);
    }

    .symbol {
      font-weight: var(--a2ui-font-medium);
      color: var(--a2ui-accent);
    }
  `;

  @property({ type: Array }) columns: TableColumn[] = [];
  @property({ type: Array }) data: Record<string, unknown>[] = [];

  private formatValue(value: unknown, key: string): string {
    if (value === null || value === undefined) return '-';
    return String(value);
  }

  private getCellClass(value: unknown, key: string): string {
    const strValue = String(value).trim();
    
    // Only style values that look like numeric changes (e.g. "+5.2%", "-1.3%")
    if (/^\+\d/.test(strValue)) return 'positive';
    if (/^-\d.*%$/.test(strValue)) return 'negative';
    
    // Style stock symbols
    if (key === 'symbol') return 'symbol';
    
    return '';
  }

  render() {
    return html`
      <table class="table">
        <thead>
          <tr>
            ${this.columns.map(col => html`
              <th 
                class="align-${col.align || 'left'}"
                style=${col.width ? `width: ${col.width}` : ''}
              >
                ${col.label}
              </th>
            `)}
          </tr>
        </thead>
        <tbody>
          ${this.data.map(row => html`
            <tr>
              ${this.columns.map(col => html`
                <td class="align-${col.align || 'left'} ${this.getCellClass(row[col.key], col.key)}">
                  ${this.formatValue(row[col.key], col.key)}
                </td>
              `)}
            </tr>
          `)}
        </tbody>
      </table>
    `;
  }
}
