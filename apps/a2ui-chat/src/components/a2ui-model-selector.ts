import { LitElement, html, css } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import type { LLMProvider, LLMModel } from '../services/chat-service';

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

    .selector-group {
      display: flex;
      align-items: center;
      gap: var(--a2ui-space-2);
    }

    label {
      font-size: var(--a2ui-text-sm);
      color: var(--a2ui-text-secondary);
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
      min-width: 140px;
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

    .provider-icon {
      width: 20px;
      height: 20px;
      border-radius: var(--a2ui-radius-sm);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 10px;
      font-weight: bold;
      display: none;
    }

    .provider-icon.openai {
      background: #10a37f;
      color: white;
    }

    .provider-icon.anthropic {
      background: #d97706;
      color: white;
    }

    .provider-icon.gemini {
      background: linear-gradient(135deg, #4285f4, #ea4335, #fbbc05, #34a853);
      color: white;
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
        min-width: 110px;
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
        max-width: 100px;
        padding: 2px var(--a2ui-space-5) 2px var(--a2ui-space-2);
        font-size: 11px;
        background-position: right 4px center;
      }

      .status {
        display: none;
      }
    }
  `;

  @property({ type: Array }) providers: LLMProvider[] = [];
  @property({ type: String }) selectedProvider = '';
  @property({ type: String }) selectedModel = '';

  @state() private models: LLMModel[] = [];

  updated(changedProperties: Map<string, unknown>) {
    if (changedProperties.has('providers') || changedProperties.has('selectedProvider')) {
      this.updateModels();
    }
  }

  private updateModels() {
    const provider = this.providers.find(p => p.id === this.selectedProvider);
    this.models = provider?.models || [];
    
    // Auto-select first model if none selected
    if (this.models.length > 0 && !this.selectedModel) {
      this.selectedModel = this.models[0].id;
      this.dispatchChange();
    }
  }

  private handleProviderChange(e: Event) {
    const select = e.target as HTMLSelectElement;
    this.selectedProvider = select.value;
    
    // Reset model selection when provider changes
    const provider = this.providers.find(p => p.id === this.selectedProvider);
    this.models = provider?.models || [];
    this.selectedModel = this.models[0]?.id || '';
    
    this.dispatchChange();
  }

  private handleModelChange(e: Event) {
    const select = e.target as HTMLSelectElement;
    this.selectedModel = select.value;
    this.dispatchChange();
  }

  private dispatchChange() {
    this.dispatchEvent(new CustomEvent('model-change', {
      detail: {
        provider: this.selectedProvider,
        model: this.selectedModel,
      },
      bubbles: true,
      composed: true,
    }));
  }

  private getProviderIcon(providerId: string) {
    switch (providerId) {
      case 'openai':
        return html`<span class="provider-icon openai">G</span>`;
      case 'anthropic':
        return html`<span class="provider-icon anthropic">C</span>`;
      case 'gemini':
        return html`<span class="provider-icon gemini">G</span>`;
      default:
        return html`<span class="provider-icon">AI</span>`;
    }
  }

  render() {
    if (this.providers.length === 0) {
      return html`
        <div class="no-providers">
          <span class="status">
            <span class="status-dot offline"></span>
            No AI providers configured
          </span>
        </div>
      `;
    }

    return html`
      <div class="selector-container">
        <div class="selector-group">
          ${this.selectedProvider ? this.getProviderIcon(this.selectedProvider) : ''}
          <select aria-label="AI provider" @change=${this.handleProviderChange}>
            <option value="" disabled ?selected=${!this.selectedProvider}>Select Provider</option>
            ${this.providers.map(p => html`
              <option value=${p.id} ?selected=${p.id === this.selectedProvider}>${p.name}</option>
            `)}
          </select>
        </div>

        ${this.models.length > 0 ? html`
          <div class="selector-group">
            <select aria-label="AI model" @change=${this.handleModelChange}>
              ${this.models.map(m => html`
                <option value=${m.id} ?selected=${m.id === this.selectedModel}>${m.name}</option>
              `)}
            </select>
          </div>
        ` : ''}

        <span class="status">
          <span class="status-dot"></span>
          Connected
        </span>
      </div>
    `;
  }
}
