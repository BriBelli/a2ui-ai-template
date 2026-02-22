import { LitElement, html, css, unsafeCSS } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { md, markdownStyles, renderMermaidDiagrams } from '../../services/markdown';

@customElement('a2ui-text')
export class A2UIText extends LitElement {
  static styles = css`
    :host {
      display: block;
    }

    .text {
      margin: 0;
      color: var(--a2ui-text-primary);
    }

    .h1 {
      font-size: var(--a2ui-text-3xl);
      font-weight: var(--a2ui-font-bold);
      line-height: var(--a2ui-leading-tight);
    }

    .h2 {
      font-size: var(--a2ui-text-2xl);
      font-weight: var(--a2ui-font-medium);
      line-height: var(--a2ui-leading-tight);
    }

    .h3 {
      font-size: var(--a2ui-text-xl);
      font-weight: var(--a2ui-font-medium);
      line-height: var(--a2ui-leading-tight);
    }

    .body {
      font-size: var(--a2ui-text-md);
      font-weight: var(--a2ui-font-normal);
      line-height: var(--a2ui-leading-normal);
    }

    .caption {
      font-size: var(--a2ui-text-sm);
      font-weight: var(--a2ui-font-normal);
      color: var(--a2ui-text-secondary);
      line-height: var(--a2ui-leading-normal);
    }

    .label {
      font-size: var(--a2ui-text-xs);
      font-weight: var(--a2ui-font-medium);
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: var(--a2ui-text-tertiary);
    }

    .code {
      font-family: var(--a2ui-font-mono);
      font-size: var(--a2ui-text-sm);
      background: var(--a2ui-bg-tertiary);
      padding: var(--a2ui-space-1) var(--a2ui-space-2);
      border-radius: var(--a2ui-radius-sm);
    }

    ${unsafeCSS(markdownStyles)}
  `;

  @property({ type: String }) content = '';
  @property({ type: String }) variant: 'h1' | 'h2' | 'h3' | 'body' | 'caption' | 'label' | 'code' = 'body';

  protected updated() {
    renderMermaidDiagrams(this.shadowRoot!);
  }

  render() {
    switch (this.variant) {
      case 'h1':
        return html`<h1 class="text h1">${this.content}</h1>`;
      case 'h2':
        return html`<h2 class="text h2">${this.content}</h2>`;
      case 'h3':
        return html`<h3 class="text h3">${this.content}</h3>`;
      case 'caption':
        return html`<span class="text caption">${md(this.content)}</span>`;
      case 'label':
        return html`<span class="text label">${this.content}</span>`;
      case 'code':
        return html`<code class="text code">${this.content}</code>`;
      default:
        return html`<div class="text body">${md(this.content)}</div>`;
    }
  }
}
