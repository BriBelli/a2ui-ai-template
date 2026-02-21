import { LitElement, html, css, unsafeCSS } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { md, markdownStyles } from '../../services/markdown';

interface ListItem {
  id: string;
  text: string;
  status?: 'pending' | 'in-progress' | 'completed';
  icon?: string;
  subtitle?: string;
}

@customElement('a2ui-list')
export class A2UIList extends LitElement {
  static styles = css`
    :host {
      display: block;
    }

    .list {
      list-style: none;
      margin: 0;
      padding: 0;
    }

    .list-item {
      display: flex;
      align-items: flex-start;
      gap: var(--a2ui-space-3);
      padding: var(--a2ui-space-2) 0;
      border-bottom: 1px solid var(--a2ui-border-subtle);
    }

    .list-item:last-child {
      border-bottom: none;
    }

    .bullet .list-item::before {
      content: "•";
      color: var(--a2ui-accent);
      font-weight: bold;
    }

    .numbered .list-item {
      counter-increment: list-counter;
    }

    .numbered .list-item::before {
      content: counter(list-counter) ".";
      color: var(--a2ui-text-secondary);
      min-width: 24px;
    }

    .numbered {
      counter-reset: list-counter;
    }

    .checkbox {
      width: 20px;
      height: 20px;
      border: 2px solid var(--a2ui-border-strong);
      border-radius: var(--a2ui-radius-sm);
      flex-shrink: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      margin-top: 2px;
    }

    .checkbox.completed {
      background: var(--a2ui-success);
      border-color: var(--a2ui-success);
    }

    .checkbox.in-progress {
      border-color: var(--a2ui-warning);
    }

    .checkmark {
      color: white;
      font-size: 12px;
    }

    .item-content {
      flex: 1;
    }

    .item-text {
      color: var(--a2ui-text-primary);
    }

    /* Strikethrough only in checklist mode */
    .checklist .item-text.completed {
      text-decoration: line-through;
      color: var(--a2ui-text-tertiary);
    }

    .item-subtitle {
      font-size: var(--a2ui-text-sm);
      color: var(--a2ui-text-secondary);
      margin-top: var(--a2ui-space-1);
    }

    .status-badge {
      font-size: var(--a2ui-text-xs);
      padding: var(--a2ui-space-1) var(--a2ui-space-2);
      border-radius: var(--a2ui-radius-full);
      text-transform: capitalize;
    }

    .status-pending {
      background: var(--a2ui-bg-tertiary);
      color: var(--a2ui-text-secondary);
    }

    .status-in-progress {
      background: var(--a2ui-warning-bg);
      color: var(--a2ui-warning);
    }

    .status-completed {
      background: var(--a2ui-success-bg);
      color: var(--a2ui-success);
    }

    ${unsafeCSS(markdownStyles)}
  `;

  @property({ type: Array }) items: ListItem[] = [];
  @property({ type: String }) variant: 'default' | 'bullet' | 'numbered' | 'checklist' = 'default';

  private renderCheckbox(status?: string) {
    const isCompleted = status === 'completed';
    const isInProgress = status === 'in-progress';
    
    return html`
      <div class="checkbox ${status || ''}">
        ${isCompleted ? html`<span class="checkmark">✓</span>` : ''}
        ${isInProgress ? html`<span class="checkmark" style="color: var(--a2ui-warning)">○</span>` : ''}
      </div>
    `;
  }

  render() {
    const listClass = `list ${this.variant}`;

    return html`
      <ul class=${listClass}>
        ${this.items.map(item => html`
          <li class="list-item">
            ${this.variant === 'checklist' ? this.renderCheckbox(item.status) : ''}
            <div class="item-content">
              <span class="item-text ${item.status === 'completed' ? 'completed' : ''}">
                ${md(item.text)}
              </span>
              ${item.subtitle ? html`
                <div class="item-subtitle">${md(item.subtitle)}</div>
              ` : ''}
            </div>
            ${item.status && this.variant !== 'checklist' ? html`
              <span class="status-badge status-${item.status}">
                ${item.status.replace('-', ' ')}
              </span>
            ` : ''}
          </li>
        `)}
      </ul>
    `;
  }
}
