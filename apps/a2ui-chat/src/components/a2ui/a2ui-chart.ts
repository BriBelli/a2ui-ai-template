import { LitElement, html, css } from 'lit';
import { customElement, property, query, state } from 'lit/decorators.js';
import {
  Chart,
  registerables,
  type ChartConfiguration,
  type Plugin,
  type TooltipItem,
} from 'chart.js';

// Register all Chart.js components
Chart.register(...registerables);

interface ChartDataset {
  label: string;
  data: number[];
  backgroundColor?: string | string[];
  borderColor?: string | string[];
  borderWidth?: number;
}

interface ChartData {
  labels: string[];
  datasets: ChartDataset[];
}

interface ChartOptions {
  height?: number;
  /** Fill area under line charts with a gradient (default: true for single-dataset line) */
  fillArea?: boolean;
  /** Show grid lines (default: false for line, true for bar) */
  showGrid?: boolean;
  /** Show the legend (default: auto -- hidden for single dataset) */
  showLegend?: boolean;
  /** Format values as currency */
  currency?: string;
  /** Show a horizontal reference line at this value */
  referenceLine?: number;
  /** Label for the reference line */
  referenceLabel?: string;
}

/**
 * Crosshair plugin -- draws a vertical dashed line at the hovered point.
 * Gives that Google Finance feel on line charts.
 */
const crosshairPlugin: Plugin = {
  id: 'a2uiCrosshair',
  afterDraw(chart) {
    const tooltip = chart.tooltip;
    if (!tooltip || !tooltip.getActiveElements().length) return;
    if (chart.config.type !== 'line') return;

    const ctx = chart.ctx;
    const x = tooltip.caretX;
    const topY = chart.scales.y.top;
    const bottomY = chart.scales.y.bottom;

    ctx.save();
    ctx.beginPath();
    ctx.moveTo(x, topY);
    ctx.lineTo(x, bottomY);
    ctx.lineWidth = 1;
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.2)';
    ctx.setLineDash([4, 4]);
    ctx.stroke();
    ctx.restore();
  },
};

/**
 * Reference line plugin -- draws a horizontal dotted line (e.g. "Previous close").
 */
const referenceLinePlugin: Plugin = {
  id: 'a2uiReferenceLine',
  afterDraw(chart) {
    const meta = (chart.config.options as Record<string, unknown>)?.plugins as Record<string, unknown> | undefined;
    const refConfig = meta?.a2uiReferenceLine as { value?: number; label?: string } | undefined;
    if (!refConfig?.value) return;

    const ctx = chart.ctx;
    const yScale = chart.scales.y;
    const y = yScale.getPixelForValue(refConfig.value);

    ctx.save();
    ctx.beginPath();
    ctx.moveTo(chart.chartArea.left, y);
    ctx.lineTo(chart.chartArea.right, y);
    ctx.lineWidth = 1;
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.15)';
    ctx.setLineDash([3, 5]);
    ctx.stroke();

    if (refConfig.label) {
      ctx.fillStyle = 'rgba(154, 160, 166, 0.8)';
      ctx.font = '10px Google Sans, Roboto, sans-serif';
      ctx.textAlign = 'right';
      ctx.fillText(
        refConfig.label,
        chart.chartArea.right - 4,
        y - 5,
      );
    }
    ctx.restore();
  },
};

Chart.register(crosshairPlugin, referenceLinePlugin);

@customElement('a2ui-chart')
export class A2UIChart extends LitElement {
  static styles = css`
    :host {
      display: block;
    }

    .chart-container {
      background: var(--a2ui-bg-tertiary);
      border-radius: var(--a2ui-radius-lg);
      padding: var(--a2ui-space-5);
      transition: box-shadow 0.2s ease;
    }

    .chart-container:hover {
      box-shadow: 0 2px 12px rgba(0, 0, 0, 0.3);
    }

    .chart-header {
      display: flex;
      align-items: baseline;
      gap: var(--a2ui-space-3);
      margin-bottom: var(--a2ui-space-3);
    }

    .chart-title {
      font-size: var(--a2ui-text-md);
      font-weight: var(--a2ui-font-medium);
      color: var(--a2ui-text-primary);
    }

    .chart-subtitle {
      font-size: var(--a2ui-text-xs);
      color: var(--a2ui-text-tertiary);
    }

    .chart-wrapper {
      position: relative;
    }

    canvas {
      width: 100% !important;
    }
  `;

  @property({ type: String }) chartType: 'bar' | 'line' | 'pie' | 'doughnut' = 'bar';
  @property({ type: String }) title = '';
  @property({ type: Object }) data: ChartData = { labels: [], datasets: [] };
  @property({ type: Object }) options: ChartOptions = {};

  @query('canvas') private canvas!: HTMLCanvasElement;
  @state() private chart?: Chart;

  // Default palette -- muted yet vibrant, works great on dark backgrounds
  private palette = [
    '#8ab4f8', // blue
    '#81c995', // green
    '#f28b82', // red
    '#fdd663', // yellow
    '#c58af9', // purple
    '#78d9ec', // teal
    '#ff8bcb', // pink
    '#fcad70', // orange
  ];

  disconnectedCallback() {
    super.disconnectedCallback();
    this.chart?.destroy();
  }

  updated(changedProperties: Map<string, unknown>) {
    if (changedProperties.has('data') || changedProperties.has('chartType') || changedProperties.has('options')) {
      this.renderChart();
    }
  }

  firstUpdated() {
    this.renderChart();
  }

  private getColor(index: number): string {
    return this.palette[index % this.palette.length];
  }

  /**
   * Create a vertical gradient for area fills under line charts
   */
  private createGradient(ctx: CanvasRenderingContext2D, color: string, height: number): CanvasGradient {
    const gradient = ctx.createLinearGradient(0, 0, 0, height);
    gradient.addColorStop(0, this.hexToRgba(color, 0.25));
    gradient.addColorStop(0.6, this.hexToRgba(color, 0.06));
    gradient.addColorStop(1, this.hexToRgba(color, 0));
    return gradient;
  }

  private hexToRgba(hex: string, alpha: number): string {
    // Handle named colors or already rgba
    if (!hex.startsWith('#')) return hex;
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  }

  private formatValue(value: number): string {
    if (this.options.currency) {
      return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: this.options.currency,
        minimumFractionDigits: 0,
        maximumFractionDigits: 2,
      }).format(value);
    }
    return value.toLocaleString();
  }

  private renderChart() {
    if (!this.canvas) return;

    this.chart?.destroy();
    const ctx = this.canvas.getContext('2d');
    if (!ctx) return;

    const isLine = this.chartType === 'line';
    const isBar = this.chartType === 'bar';
    const isPie = this.chartType === 'pie' || this.chartType === 'doughnut';
    const isSingleDataset = this.data.datasets.length === 1;
    const chartHeight = this.options.height || 240;

    // Determine whether to fill area under lines
    const shouldFill = isLine && (this.options.fillArea !== undefined ? this.options.fillArea : isSingleDataset);

    // Determine grid visibility
    const showGrid = this.options.showGrid !== undefined ? this.options.showGrid : isBar;

    // Determine legend visibility
    const showLegend = this.options.showLegend !== undefined
      ? this.options.showLegend
      : (isPie || this.data.datasets.length > 1);

    // Build datasets
    const datasets = this.data.datasets.map((ds, i) => {
      const color = (ds.borderColor as string) || this.getColor(i);
      const bgColor = ds.backgroundColor || (isLine
        ? (shouldFill ? this.createGradient(ctx, color, chartHeight) : 'transparent')
        : isPie ? this.palette.slice(0, this.data.labels.length) : this.hexToRgba(color, 0.7));

      return {
        ...ds,
        borderColor: color,
        backgroundColor: bgColor,
        borderWidth: ds.borderWidth ?? (isLine ? 2.5 : 0),
        tension: isLine ? 0.35 : undefined,
        fill: isLine ? shouldFill : undefined,
        pointRadius: isLine ? 0 : undefined,
        pointHoverRadius: isLine ? 5 : undefined,
        pointHoverBackgroundColor: isLine ? color : undefined,
        pointHoverBorderColor: isLine ? '#1a1a1a' : undefined,
        pointHoverBorderWidth: isLine ? 2 : undefined,
        borderRadius: isBar ? 4 : undefined,
        maxBarThickness: isBar ? 48 : undefined,
      };
    });

    const self = this;

    const config: ChartConfiguration = {
      type: this.chartType,
      data: {
        labels: this.data.labels,
        datasets,
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: {
          duration: 600,
          easing: 'easeOutQuart',
        },
        interaction: {
          mode: isLine ? 'index' : 'nearest',
          intersect: !isLine,
        },
        layout: {
          padding: {
            top: 4,
            right: 4,
            bottom: 0,
            left: 4,
          },
        },
        plugins: {
          legend: {
            display: showLegend,
            position: 'bottom',
            labels: {
              color: '#9aa0a6',
              padding: 16,
              usePointStyle: true,
              pointStyle: 'circle',
              boxWidth: 8,
              boxHeight: 8,
              font: {
                family: 'Google Sans, Roboto, sans-serif',
                size: 11,
              },
            },
          },
          tooltip: {
            enabled: true,
            backgroundColor: 'rgba(32, 33, 36, 0.95)',
            titleColor: '#e3e3e3',
            bodyColor: '#9aa0a6',
            borderColor: 'rgba(255, 255, 255, 0.1)',
            borderWidth: 1,
            cornerRadius: 8,
            padding: { top: 8, bottom: 8, left: 12, right: 12 },
            titleFont: {
              family: 'Google Sans, Roboto, sans-serif',
              size: 12,
              weight: 'bold' as const,
            },
            bodyFont: {
              family: 'Google Sans, Roboto, sans-serif',
              size: 11,
            },
            displayColors: this.data.datasets.length > 1,
            boxWidth: 8,
            boxHeight: 8,
            boxPadding: 4,
            usePointStyle: true,
            callbacks: {
              label(context: TooltipItem<'bar' | 'line' | 'pie' | 'doughnut'>) {
                const label = context.dataset.label || '';
                const value = self.formatValue(context.parsed.y ?? (context.parsed as unknown as number));
                return label ? `${label}: ${value}` : value;
              },
            },
          },
          // Pass reference line config via plugin options
          a2uiReferenceLine: this.options.referenceLine
            ? { value: this.options.referenceLine, label: this.options.referenceLabel }
            : undefined,
        } as Record<string, unknown>,
        scales: !isPie ? {
          x: {
            grid: {
              display: showGrid,
              color: 'rgba(255, 255, 255, 0.04)',
              drawTicks: false,
            },
            border: {
              display: false,
            },
            ticks: {
              color: '#71767b',
              maxRotation: 0,
              padding: 8,
              font: {
                family: 'Google Sans, Roboto, sans-serif',
                size: 10,
              },
              autoSkip: true,
              maxTicksLimit: 8,
            },
          },
          y: {
            grid: {
              display: true,
              color: 'rgba(255, 255, 255, 0.04)',
              drawTicks: false,
            },
            border: {
              display: false,
            },
            ticks: {
              color: '#71767b',
              padding: 8,
              font: {
                family: 'Google Sans, Roboto, sans-serif',
                size: 10,
              },
              callback: (value: string | number) => self.formatValue(Number(value)),
            },
          },
        } : undefined,
      },
    };

    this.chart = new Chart(ctx, config);
  }

  render() {
    const height = this.options.height || 240;

    return html`
      <div class="chart-container">
        ${this.title ? html`
          <div class="chart-header">
            <span class="chart-title">${this.title}</span>
          </div>
        ` : ''}
        <div class="chart-wrapper" style="height: ${height}px">
          <canvas></canvas>
        </div>
      </div>
    `;
  }
}
