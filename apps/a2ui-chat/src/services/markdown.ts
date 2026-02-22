/**
 * Markdown rendering utility for A2UI.
 *
 * Converts markdown strings to sanitized HTML using `marked` + `DOMPurify`.
 * Supports mermaid diagram code blocks via lazy-loaded mermaid library.
 * Used for inline/paragraph formatting within A2UI components — the A2UI
 * component system still owns layout and data visualization.
 */

import { marked } from 'marked';
import DOMPurify from 'dompurify';
import { html, type TemplateResult } from 'lit';
import { unsafeHTML } from 'lit/directives/unsafe-html.js';

let mermaidCounter = 0;
let mermaidReady: Promise<typeof import('mermaid')> | null = null;

function ensureMermaid(): Promise<typeof import('mermaid')> {
  if (!mermaidReady) {
    mermaidReady = import('mermaid').then((m) => {
      m.default.initialize({
        startOnLoad: false,
        theme: 'dark',
        themeVariables: {
          primaryColor: '#3d4f6f',
          primaryTextColor: '#e3e3e3',
          primaryBorderColor: '#5a6a8a',
          lineColor: '#71767b',
          secondaryColor: '#2a2a2a',
          tertiaryColor: '#1e1e1e',
          fontFamily: 'Google Sans, Roboto, sans-serif',
          fontSize: '13px',
        },
      });
      return m;
    });
  }
  return mermaidReady;
}

/**
 * Render any pending mermaid diagrams in the DOM.
 * Call after inserting markdown HTML that may contain mermaid placeholders.
 */
export async function renderMermaidDiagrams(root: HTMLElement | ShadowRoot): Promise<void> {
  const containers = root.querySelectorAll<HTMLElement>('.mermaid-container[data-mermaid]');
  if (containers.length === 0) return;

  try {
    const m = await ensureMermaid();
    for (const el of containers) {
      const code = el.getAttribute('data-mermaid');
      if (!code || el.querySelector('svg')) continue;

      const id = `mermaid-${++mermaidCounter}`;
      try {
        const { svg } = await m.default.render(id, code);
        el.innerHTML = svg;
        el.removeAttribute('data-mermaid');
      } catch {
        el.innerHTML = `<pre class="mermaid-error"><code>${DOMPurify.sanitize(code)}</code></pre>`;
        el.removeAttribute('data-mermaid');
      }
    }
  } catch {
    // mermaid failed to load — leave raw code blocks
  }
}

marked.setOptions({
  breaks: true,
  gfm: true,
});

const MERMAID_BLOCK_RE = /```mermaid\s*\n([\s\S]*?)```/g;

/**
 * Parse a markdown string into sanitized HTML.
 * Mermaid code blocks are converted to placeholder divs for async rendering.
 * Returns an empty string for falsy input.
 */
export function renderMarkdown(text: string): string {
  if (!text) return '';

  // Extract mermaid blocks before marked processes them
  const mermaidBlocks: string[] = [];
  const processed = text.replace(MERMAID_BLOCK_RE, (_match, code: string) => {
    const idx = mermaidBlocks.length;
    mermaidBlocks.push(code.trim());
    return `\n<div class="mermaid-placeholder" data-idx="${idx}"></div>\n`;
  });

  const raw = marked.parse(processed, { async: false }) as string;
  let sanitized = DOMPurify.sanitize(raw, {
    ALLOWED_TAGS: [
      'p', 'br', 'strong', 'b', 'em', 'i', 'a', 'code', 'pre',
      'blockquote', 'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4',
      'del', 'hr', 'span', 'div',
    ],
    ALLOWED_ATTR: ['href', 'target', 'rel', 'class', 'data-idx', 'data-mermaid'],
  });

  // Replace placeholders with mermaid containers carrying the diagram source
  for (let i = 0; i < mermaidBlocks.length; i++) {
    const escaped = mermaidBlocks[i]
      .replace(/&/g, '&amp;')
      .replace(/"/g, '&quot;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
    sanitized = sanitized.replace(
      new RegExp(`<div class="mermaid-placeholder" data-idx="${i}"></div>`),
      `<div class="mermaid-container" data-mermaid="${escaped}"><div class="mermaid-loading">Loading diagram…</div></div>`,
    );
  }

  return sanitized;
}

/**
 * Render a markdown string as a Lit `TemplateResult`.
 * Wraps the sanitized HTML in a `.md` container for scoped styling.
 */
export function md(text: string): TemplateResult {
  if (!text) return html``;
  const sanitized = renderMarkdown(text);
  return html`<span class="md">${unsafeHTML(sanitized)}</span>`;
}

/**
 * Shared CSS for markdown-rendered content.
 * Import this into any component that uses `md()` or `renderMarkdown()`.
 */
export const markdownStyles = `
  .md { display: contents; }

  .md p {
    margin: 0 0 0.5em 0;
    line-height: var(--a2ui-leading-relaxed, 1.7);
  }

  .md p:last-child { margin-bottom: 0; }

  .md strong, .md b {
    font-weight: var(--a2ui-font-semibold, 600);
    color: var(--a2ui-text-primary);
  }

  .md em, .md i {
    font-style: italic;
  }

  .md a {
    color: var(--a2ui-accent, #4285f4);
    text-decoration: none;
  }

  .md a:hover {
    text-decoration: underline;
  }

  .md code {
    font-family: var(--a2ui-font-mono, monospace);
    font-size: 0.875em;
    background: var(--a2ui-bg-tertiary, rgba(255,255,255,0.06));
    padding: 0.15em 0.4em;
    border-radius: var(--a2ui-radius-sm, 4px);
  }

  .md pre {
    background: var(--a2ui-bg-tertiary, rgba(255,255,255,0.06));
    padding: var(--a2ui-space-3, 12px);
    border-radius: var(--a2ui-radius-md, 8px);
    overflow-x: auto;
    margin: 0.5em 0;
  }

  .md pre code {
    background: none;
    padding: 0;
    font-size: 0.85em;
    line-height: 1.5;
  }

  .md blockquote {
    margin: 0.5em 0;
    padding: 0.25em 0 0.25em 1em;
    border-left: 3px solid var(--a2ui-border-strong, rgba(255,255,255,0.15));
    color: var(--a2ui-text-secondary);
    font-style: italic;
  }

  .md ul, .md ol {
    margin: 0.25em 0;
    padding-left: 1.5em;
  }

  .md li {
    margin-bottom: 0.25em;
    line-height: var(--a2ui-leading-relaxed, 1.7);
  }

  .md h1, .md h2, .md h3, .md h4 {
    margin: 0.75em 0 0.25em 0;
    font-weight: var(--a2ui-font-semibold, 600);
    color: var(--a2ui-text-primary);
    line-height: var(--a2ui-leading-tight, 1.25);
  }

  .md h1 { font-size: var(--a2ui-text-xl, 1.25rem); }
  .md h2 { font-size: var(--a2ui-text-lg, 1.125rem); }
  .md h3 { font-size: var(--a2ui-text-md, 1rem); }
  .md h4 { font-size: var(--a2ui-text-sm, 0.875rem); }

  .md h1:first-child, .md h2:first-child, .md h3:first-child {
    margin-top: 0;
  }

  .md del {
    text-decoration: line-through;
    color: var(--a2ui-text-tertiary);
  }

  .md hr {
    border: none;
    border-top: 1px solid var(--a2ui-border-default);
    margin: 0.75em 0;
  }

  /* ── Mermaid diagrams ─────────────────────────── */

  .md .mermaid-container {
    margin: 0.75em 0;
    padding: var(--a2ui-space-4, 16px);
    background: var(--a2ui-bg-tertiary, rgba(255,255,255,0.06));
    border-radius: var(--a2ui-radius-lg, 12px);
    overflow-x: auto;
    display: flex;
    justify-content: center;
  }

  .md .mermaid-container svg {
    max-width: 100%;
    height: auto;
  }

  .md .mermaid-loading {
    color: var(--a2ui-text-tertiary);
    font-size: var(--a2ui-text-sm, 0.875rem);
    padding: var(--a2ui-space-3, 12px) 0;
  }

  .md .mermaid-error {
    color: var(--a2ui-text-secondary);
    font-size: var(--a2ui-text-xs, 0.75rem);
    margin: 0;
  }
`;
