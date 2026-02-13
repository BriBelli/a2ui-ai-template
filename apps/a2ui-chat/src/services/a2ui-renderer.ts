import { html, TemplateResult, nothing } from 'lit';
import type { A2UIResponse, A2UIComponent } from '@a2ui/core';

/**
 * A2UI Renderer for Lit Web Components
 *
 * This service maps A2UI protocol components to their
 * Lit Web Component implementations.
 */
export class A2UIRenderer {
  /**
   * Render an A2UI response to Lit templates.
   *
   * Consecutive top-level `stat` components are automatically grouped
   * into a horizontal grid row so they sit side-by-side on desktop
   * and stack on narrow / mobile viewports.
   */
  static render(response: A2UIResponse): TemplateResult {
    if (!response || !response.components) {
      return html`${nothing}`;
    }

    // Group consecutive stat components into grid wrappers
    const grouped = this.groupConsecutiveStats(response.components);

    return html`
      <div class="a2ui-root" style="display:flex; flex-direction:column; gap:16px">
        ${grouped.map((item) => {
          if (Array.isArray(item)) {
            // Stat group → render as a horizontal grid
            const cols = Math.min(item.length, 6);
            return html`
              <a2ui-grid
                .columns=${String(cols)}
                .spacing=${'lg'}
                .minItemWidth=${'180px'}
              >
                ${item.map((c) => this.renderComponent(c))}
              </a2ui-grid>
            `;
          }
          return this.renderComponent(item);
        })}
      </div>
    `;
  }

  /**
   * Walk the components array and collect runs of consecutive `stat`
   * components into sub-arrays.  Non-stat components pass through as-is.
   *
   * e.g. [stat, stat, stat, chart, table]
   *   → [[stat, stat, stat], chart, table]
   */
  private static groupConsecutiveStats(
    components: A2UIComponent[]
  ): (A2UIComponent | A2UIComponent[])[] {
    const result: (A2UIComponent | A2UIComponent[])[] = [];
    let statRun: A2UIComponent[] = [];

    for (const c of components) {
      if (c && typeof c === 'object' && c.type === 'stat') {
        statRun.push(c);
      } else {
        // Flush any accumulated stat run
        if (statRun.length > 1) {
          result.push(statRun);
        } else if (statRun.length === 1) {
          // Single stat — no need to grid-wrap, render normally
          result.push(statRun[0]);
        }
        statRun = [];
        result.push(c);
      }
    }

    // Flush trailing stats
    if (statRun.length > 1) {
      result.push(statRun);
    } else if (statRun.length === 1) {
      result.push(statRun[0]);
    }

    return result;
  }

  /**
   * Render a single A2UI component
   */
  static renderComponent(component: A2UIComponent): TemplateResult {
    if (!component || typeof component !== 'object') {
      console.warn('Invalid component:', component);
      return html`${nothing}`;
    }

    const { type, id, props = {} } = component;
    // Children can be inline A2UIComponent[] (LLM output) or string[] (flat mode)
    const children = (component.children ?? []) as A2UIComponent[];

    // Skip components without a type
    if (!type) {
      console.warn('Component missing type:', component);
      return html`${nothing}`;
    }

    // Render children recursively
    const renderedChildren = Array.isArray(children)
      ? children.map((child) => this.renderComponent(child))
      : [];

    switch (type) {
      case 'text':
        return html`
          <a2ui-text
            .id=${id}
            .content=${props.content || ''}
            .variant=${props.variant || 'body'}
          ></a2ui-text>
        `;

      case 'container':
        return html`
          <a2ui-container
            .id=${id}
            .layout=${props.layout || 'vertical'}
            .spacing=${props.gap || 'md'}
            .wrap=${props.wrap || false}
          >
            ${renderedChildren}
          </a2ui-container>
        `;

      case 'grid':
        return html`
          <a2ui-grid
            .id=${id}
            .columns=${props.columns ?? 'auto'}
            .spacing=${props.gap || 'lg'}
            .minItemWidth=${props.minItemWidth || '150px'}
          >
            ${renderedChildren}
          </a2ui-grid>
        `;

      case 'card':
        return html`
          <a2ui-card
            .id=${id}
            .cardTitle=${props.title || ''}
            .subtitle=${props.subtitle || ''}
          >
            ${renderedChildren}
          </a2ui-card>
        `;

      case 'list':
        return html`
          <a2ui-list
            .id=${id}
            .items=${props.items || []}
            .variant=${props.variant || 'default'}
          ></a2ui-list>
        `;

      case 'data-table':
        return html`
          <a2ui-data-table
            .id=${id}
            .columns=${props.columns || []}
            .data=${props.data || []}
          ></a2ui-data-table>
        `;

      case 'chart':
        return html`
          <a2ui-chart
            .id=${id}
            .chartType=${props.chartType || 'bar'}
            .title=${props.title || ''}
            .data=${props.data || {}}
            .options=${props.options || {}}
          ></a2ui-chart>
        `;

      case 'link':
        return html`
          <a2ui-link
            .id=${id}
            .href=${props.href || '#'}
            .text=${props.text || ''}
            .external=${props.external || false}
          ></a2ui-link>
        `;

      case 'chip':
        return html`
          <a2ui-chip
            .id=${id}
            .label=${props.label || ''}
            .variant=${props.variant || 'default'}
            .clickable=${props.clickable || false}
          ></a2ui-chip>
        `;

      case 'button':
        return html`
          <a2ui-button
            .id=${id}
            .label=${props.label || ''}
            .variant=${props.variant || 'default'}
            .disabled=${props.disabled || false}
          ></a2ui-button>
        `;

      case 'image':
        return html`
          <a2ui-image
            .id=${id}
            .src=${props.src || props.url || ''}
            .alt=${props.alt || props.caption || ''}
            .caption=${props.caption || ''}
          ></a2ui-image>
        `;

      /* ── New Atomic / Molecular components ── */

      case 'stat':
        return html`
          <a2ui-stat
            .id=${id}
            .label=${props.label || ''}
            .value=${props.value || ''}
            .trend=${props.trend || ''}
            .trendDirection=${props.trendDirection || 'neutral'}
            .description=${props.description || ''}
          ></a2ui-stat>
        `;

      case 'separator':
        return html`
          <a2ui-separator
            .id=${id}
            .orientation=${props.orientation || 'horizontal'}
            .label=${props.label || ''}
          ></a2ui-separator>
        `;

      case 'progress':
        return html`
          <a2ui-progress
            .id=${id}
            .label=${props.label || ''}
            .value=${props.value || 0}
            .max=${props.max || 100}
            .variant=${props.variant || 'default'}
            .showValue=${props.showValue !== false}
          ></a2ui-progress>
        `;

      case 'accordion':
        return html`
          <a2ui-accordion
            .id=${id}
            .items=${props.items || []}
            .multiple=${props.multiple || false}
          ></a2ui-accordion>
        `;

      case 'tabs':
        return html`
          <a2ui-tabs
            .id=${id}
            .tabs=${props.tabs || []}
          ></a2ui-tabs>
        `;

      case 'alert':
        return html`
          <a2ui-alert
            .id=${id}
            .variant=${props.variant || 'default'}
            .alertTitle=${props.title || ''}
            .description=${props.description || ''}
          ></a2ui-alert>
        `;

      default:
        console.warn(`Unknown A2UI component type: ${type}`);
        return html`
          <div class="a2ui-unknown">
            Unknown component: ${type}
          </div>
        `;
    }
  }
}
