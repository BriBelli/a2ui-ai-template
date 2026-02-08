import { LitElement, html, css } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';

@customElement('a2ui-image')
export class A2UIImage extends LitElement {
  static styles = css`
    :host {
      display: block;
    }

    .image-container {
      position: relative;
      overflow: hidden;
      border-radius: var(--a2ui-radius-md);
      background: var(--a2ui-bg-tertiary);
    }

    img {
      display: block;
      width: 100%;
      height: auto;
      object-fit: cover;
      transition: opacity var(--a2ui-transition-normal);
    }

    img.loading {
      opacity: 0;
    }

    img.loaded {
      opacity: 1;
    }

    img.error {
      display: none;
    }

    .placeholder {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: var(--a2ui-space-2);
      width: 100%;
      padding: var(--a2ui-space-6) var(--a2ui-space-4);
      background: linear-gradient(135deg, var(--a2ui-bg-tertiary), var(--a2ui-bg-elevated));
      color: var(--a2ui-text-tertiary);
      font-size: var(--a2ui-text-2xl);
    }

    .placeholder-alt {
      font-size: var(--a2ui-text-sm);
      color: var(--a2ui-text-tertiary);
      text-align: center;
    }

    .caption {
      margin-top: var(--a2ui-space-2);
      font-size: var(--a2ui-text-sm);
      color: var(--a2ui-text-secondary);
      text-align: center;
    }
  `;

  @property({ type: String }) src = '';
  @property({ type: String }) alt = '';
  @property({ type: String }) caption = '';
  @property({ type: String }) fallbackIcon = '🖼️';

  @state() private loadState: 'loading' | 'loaded' | 'error' = 'loading';

  /**
   * Validate image src to prevent javascript:, file:, and other dangerous protocols.
   * Allows: http(s), relative paths, and data:image/* URIs.
   */
  private isValidSrc(src: string): boolean {
    if (!src) return false;
    const trimmed = src.trim().toLowerCase();

    // Allow relative paths
    if (trimmed.startsWith('/') || trimmed.startsWith('./') || trimmed.startsWith('../')) return true;
    // Allow http(s)
    if (trimmed.startsWith('http://') || trimmed.startsWith('https://')) return true;
    // Allow base64 images specifically (data:image/png, data:image/jpeg, etc.)
    if (trimmed.startsWith('data:image/')) return true;

    // Block everything else (javascript:, file:, data:text/html, etc.)
    return false;
  }

  private handleLoad() {
    this.loadState = 'loaded';
  }

  private handleError() {
    this.loadState = 'error';
  }

  render() {
    const showPlaceholder = !this.src || !this.isValidSrc(this.src) || this.loadState === 'error';

    return html`
      <div class="image-container">
        ${showPlaceholder ? html`
          <div class="placeholder">
            ${this.fallbackIcon}
            ${this.alt ? html`<span class="placeholder-alt">${this.alt}</span>` : ''}
          </div>
        ` : html`
          <img
            class=${this.loadState}
            src=${this.src}
            alt=${this.alt}
            @load=${this.handleLoad}
            @error=${this.handleError}
          />
        `}
      </div>
      ${this.caption ? html`
        <div class="caption">${this.caption}</div>
      ` : ''}
    `;
  }
}
