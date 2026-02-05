import { LitElement, html, css } from 'lit';
import { customElement, property } from 'lit/decorators.js';

/** Protocols allowed in href values. Everything else is blocked. */
const SAFE_PROTOCOLS = ['http:', 'https:', 'mailto:'];

@customElement('a2ui-link')
export class A2UILink extends LitElement {
  static styles = css`
    :host {
      display: inline;
    }

    a {
      color: var(--a2ui-link);
      text-decoration: none;
      transition: color var(--a2ui-transition-fast);
    }

    a:hover {
      color: var(--a2ui-link-hover);
      text-decoration: underline;
    }

    .external-icon {
      display: inline-block;
      width: 12px;
      height: 12px;
      margin-left: var(--a2ui-space-1);
      vertical-align: middle;
    }
  `;

  @property({ type: String }) href = '#';
  @property({ type: String }) text = '';
  @property({ type: Boolean }) external = false;

  /**
   * Sanitize href to prevent javascript:, data:, vbscript:, file: XSS vectors.
   * Only allows http(s), mailto, relative paths, and fragment links.
   */
  private sanitizeHref(href: string): string {
    const trimmed = href.trim();

    // Allow fragment-only and relative paths
    if (trimmed.startsWith('#') || trimmed.startsWith('/') || trimmed.startsWith('./') || trimmed.startsWith('../')) {
      return trimmed;
    }

    // Check protocol for absolute URLs
    try {
      const url = new URL(trimmed, window.location.href);
      if (SAFE_PROTOCOLS.includes(url.protocol)) {
        return trimmed;
      }
    } catch {
      // Malformed URL — fall through to blocked
    }

    // Block everything else
    return '#';
  }

  render() {
    const safeHref = this.sanitizeHref(this.href);

    return html`
      <a 
        href=${safeHref}
        target=${this.external ? '_blank' : '_self'}
        rel=${this.external ? 'noopener noreferrer' : ''}
      >
        ${this.text || html`<slot></slot>`}
        ${this.external ? html`
          <svg class="external-icon" viewBox="0 0 24 24" fill="currentColor">
            <path d="M19 19H5V5h7V3H5a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7h-2v7zM14 3v2h3.59l-9.83 9.83 1.41 1.41L19 6.41V10h2V3h-7z"/>
          </svg>
        ` : ''}
      </a>
    `;
  }
}
