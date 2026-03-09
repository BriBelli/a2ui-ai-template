import { LitElement, html, css } from 'lit';
import { customElement, property, query, state } from 'lit/decorators.js';
import {
  Chart,
  registerables,
  type ChartConfiguration,
  type Plugin,
  type TooltipItem,
} from 'chart.js';
import { TreemapController, TreemapElement } from 'chartjs-chart-treemap';
import { SankeyController, Flow } from 'chartjs-chart-sankey';
import { FunnelController, TrapezoidElement } from 'chartjs-chart-funnel';
import { MatrixController, MatrixElement } from 'chartjs-chart-matrix';
import {
  ChoroplethController,
  BubbleMapController,
  GeoFeature,
  ColorScale,
  ProjectionScale,
  SizeScale,
} from 'chartjs-chart-geo';
import * as topojson from 'topojson-client';
import type { Topology } from 'topojson-specification';

Chart.register(
  ...registerables,
  TreemapController, TreemapElement,
  SankeyController, Flow,
  FunnelController, TrapezoidElement,
  MatrixController, MatrixElement,
  ChoroplethController, BubbleMapController, GeoFeature,
  ColorScale, ProjectionScale, SizeScale,
);

interface ChartDataset {
  label: string;
  data: number[] | Array<{ x: number; y: number; r?: number }>;
  backgroundColor?: string | string[];
  borderColor?: string | string[];
  borderWidth?: number;
}

interface ChartData {
  labels?: string[];
  datasets: ChartDataset[];
  /** For geo charts: which map to render ("world" | "us-states") */
  map?: string;
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
  /** Label for the X axis (e.g. "Stock Ticker", "Month") */
  xAxisLabel?: string;
  /** Label for the Y axis (e.g. "Price (USD)", "Trending Score") */
  yAxisLabel?: string;
}

/** Read a CSS custom property from :root. */
function rootToken(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
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
    if (!('type' in chart.config) || chart.config.type !== 'line') return;

    const ctx = chart.ctx;
    const x = tooltip.caretX;
    const topY = chart.scales.y.top;
    const bottomY = chart.scales.y.bottom;

    ctx.save();
    ctx.beginPath();
    ctx.moveTo(x, topY);
    ctx.lineTo(x, bottomY);
    ctx.lineWidth = 1;
    ctx.strokeStyle = rootToken('--a2ui-border-strong') || 'rgba(255, 255, 255, 0.2)';
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
    ctx.strokeStyle = rootToken('--a2ui-border-default') || 'rgba(255, 255, 255, 0.15)';
    ctx.setLineDash([3, 5]);
    ctx.stroke();

    if (refConfig.label) {
      ctx.fillStyle = rootToken('--a2ui-text-secondary') || 'rgba(154, 160, 166, 0.8)';
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
      box-shadow: var(--a2ui-shadow-lg);
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

    .geo-loading {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      color: var(--a2ui-text-tertiary);
      font-size: var(--a2ui-text-sm);
      font-family: 'Google Sans', Roboto, sans-serif;
    }

    .geo-loading .spinner {
      width: 16px;
      height: 16px;
      border: 2px solid var(--a2ui-border-subtle, rgba(255,255,255,0.1));
      border-top-color: var(--a2ui-text-tertiary, #71767b);
      border-radius: 50%;
      animation: geo-spin 0.8s linear infinite;
    }

    @keyframes geo-spin {
      to { transform: rotate(360deg); }
    }
  `;

  @property({ type: String }) chartType: 'bar' | 'line' | 'pie' | 'doughnut' | 'radar' | 'polarArea' | 'scatter' | 'bubble' | 'treemap' | 'sankey' | 'funnel' | 'matrix' | 'choropleth' | 'bubbleMap' = 'bar';
  @property({ type: String }) title = '';
  @property({ type: Object }) data: ChartData = { labels: undefined, datasets: [] };
  @property({ type: Object }) options: ChartOptions = {};

  @query('canvas') private canvas!: HTMLCanvasElement;

  /** Not reactive — the Chart.js instance is imperative and never referenced
   *  in the template, so @state() would only cause a spurious re-render. */
  private chart?: Chart;

  @state() private _geoLoading = false;

  /** Row labels (y-axis categories) extracted by normalizeMatrixData. */
  private _matrixRows: string[] = [];

  private static _mapCache = new Map<string, { features: GeoJSON.Feature[]; outline: GeoJSON.Feature }>();

  private static MAP_SOURCES: Record<string, { url: string; featureKey: string; outlineKey: string }> = {
    world: {
      url: '/maps/countries-110m.json',
      featureKey: 'countries',
      outlineKey: 'land',
    },
    'us-states': {
      url: '/maps/states-10m.json',
      featureKey: 'states',
      outlineKey: 'nation',
    },
  };

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

  /** Valid ISO 4217 currency codes are 3 uppercase letters. */
  private static CURRENCY_RE = /^[A-Z]{3}$/;

  private formatValue(value: number): string {
    if (this.options.currency && A2UIChart.CURRENCY_RE.test(this.options.currency)) {
      try {
        return new Intl.NumberFormat('en-US', {
          style: 'currency',
          currency: this.options.currency,
          minimumFractionDigits: 0,
          maximumFractionDigits: 2,
        }).format(value);
      } catch {
        // Fall through to default formatting if currency is unrecognised
      }
    }
    return value.toLocaleString();
  }

  /** Read a CSS custom property from the document root. */
  private token(name: string): string {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  /**
   * Normalize scatter/bubble data when the LLM sends the wrong format.
   *
   * Common misformats:
   *  A) labels[] + one dataset with flat number[] → use label index as x
   *  B) labels[] + two datasets with flat number[] → merge into {x, y} pairs
   *  C) N datasets each with a single flat number → consolidate at x=index
   *
   * Returns a cleaned copy without mutating this.data.
   */
  private normalizeScatterData(): ChartData {
    const isPointBased = this.chartType === 'scatter' || this.chartType === 'bubble';
    if (!isPointBased) return this.data;
    if (!this.data.datasets?.length) return this.data;

    const hasLabels = Array.isArray(this.data.labels) && this.data.labels.length > 0;

    const isFlat = (arr: unknown[]): arr is number[] =>
      arr.length > 0 && arr.every(v => typeof v === 'number');

    const allFlat = this.data.datasets.every(
      ds => Array.isArray(ds.data) && isFlat(ds.data as unknown[]),
    );

    if (!allFlat) return this.data;

    const dsCount = this.data.datasets.length;
    const labels = (this.data.labels ?? []).map(String);

    // Case B: exactly 2 datasets with flat numbers → treat as X-series + Y-series
    if (dsCount === 2) {
      const xData = this.data.datasets[0].data as number[];
      const yData = this.data.datasets[1].data as number[];
      const len = Math.min(xData.length, yData.length);
      const points = Array.from({ length: len }, (_, i) => ({
        x: xData[i],
        y: yData[i],
      }));

      return {
        datasets: [{
          label: this.data.datasets[1].label || this.data.datasets[0].label || '',
          data: points as unknown as number[],
        }],
      };
    }

    // Case A: labels + single dataset with flat numbers
    if (dsCount === 1 && hasLabels) {
      const nums = this.data.datasets[0].data as number[];
      const points = nums.map((v, i) => ({ x: i, y: v }));

      return {
        datasets: [{
          ...this.data.datasets[0],
          data: points as unknown as number[],
        }],
      };
    }

    // Case C: N datasets each with a single value (one per "point")
    if (dsCount > 2 && this.data.datasets.every(ds => (ds.data as number[]).length === 1)) {
      const points = this.data.datasets.map((ds, i) => ({
        x: i,
        y: (ds.data as number[])[0],
      }));

      return {
        datasets: [{
          label: '',
          data: points as unknown as number[],
        }],
      };
    }

    return this.data;
  }

  /**
   * Normalize matrix data into a single dense grid.
   * Returns a cleaned copy without mutating this.data (avoids re-render loop).
   */
  private normalizeMatrixData(): ChartData {
    if (this.chartType !== 'matrix') return this.data;
    if (!this.data.datasets?.length) return this.data;

    // Merge ALL datasets into one flat point array
    const allPoints: Array<{ x: string; y: string; v: number }> = [];
    for (const ds of this.data.datasets) {
      if (!Array.isArray(ds.data)) continue;
      for (const raw of ds.data as unknown[]) {
        if (!raw || typeof raw !== 'object') continue;
        const obj = raw as Record<string, unknown>;
        const v = typeof obj.v === 'number' ? obj.v : undefined;
        if (v === undefined) continue;

        const x = obj.x != null ? String(obj.x) : undefined;
        const y = obj.y != null ? String(obj.y) : undefined;
        if (x && y) allPoints.push({ x, y, v });
      }
    }

    console.log(`[a2ui-chart] Matrix normalize: ${this.data.datasets.length} datasets → ${allPoints.length} points`);
    if (allPoints.length > 0) {
      console.log('[a2ui-chart] Matrix sample point:', JSON.stringify(allPoints[0]));
    }

    if (allPoints.length === 0) {
      console.warn('[a2ui-chart] Matrix: no valid {x, y, v} points found in data');
      return this.data;
    }

    // Collect all unique values from each dimension
    const rawXVals = [...new Set(allPoints.map(p => p.x))];
    const rawYVals = [...new Set(allPoints.map(p => p.y))];

    console.log(`[a2ui-chart] Matrix dimensions: x=${rawXVals.length} [${rawXVals.slice(0, 3).join(', ')}...] y=${rawYVals.length} [${rawYVals.slice(0, 3).join(', ')}...]`);

    // Determine which dimension is columns (x-axis) vs rows (y-axis).
    // Use original labels[] as a hint if available — the LLM is told labels = x-axis only.
    const origLabels = (this.data.labels || []).map(String);
    let colVals: string[];  // x-axis (columns)
    let rowVals: string[];  // y-axis (rows)

    if (origLabels.length > 0) {
      // Trust original labels as the column definition
      const labelSet = new Set(origLabels);
      const xInLabels = rawXVals.filter(v => labelSet.has(v));
      const yInLabels = rawYVals.filter(v => labelSet.has(v));

      if (xInLabels.length >= yInLabels.length && xInLabels.length > 0) {
        // x-values match labels → correct orientation
        colVals = origLabels;
        rowVals = rawYVals;
      } else {
        // y-values match labels → axes are swapped
        console.warn('[a2ui-chart] Matrix: axes swapped (labels match y), flipping');
        colVals = origLabels;
        rowVals = rawXVals;
        for (const p of allPoints) {
          const tmp = p.x; p.x = p.y; p.y = tmp;
        }
      }
    } else {
      // No labels hint: larger unique set = columns
      if (rawXVals.length >= rawYVals.length) {
        colVals = rawXVals;
        rowVals = rawYVals;
      } else {
        console.warn('[a2ui-chart] Matrix: axes appear swapped, flipping');
        colVals = rawYVals;
        rowVals = rawXVals;
        for (const p of allPoints) {
          const tmp = p.x; p.x = p.y; p.y = tmp;
        }
      }
    }

    // Filter to only valid grid points and deduplicate
    const colSet = new Set(colVals);
    const rowSet = new Set(rowVals);
    const seen = new Map<string, { x: string; y: string; v: number }>();
    for (const p of allPoints) {
      if (colSet.has(p.x) && rowSet.has(p.y)) {
        seen.set(`${p.x}|${p.y}`, p);
      }
    }
    const finalPoints = [...seen.values()];

    console.log(`[a2ui-chart] Matrix result: ${rowVals.length} rows × ${colVals.length} cols = ${finalPoints.length} cells`);

    this._matrixRows = rowVals;

    const firstDs = this.data.datasets[0];
    return {
      ...this.data,
      labels: colVals,
      datasets: [{ ...firstDs, data: finalPoints as unknown as number[] }],
    };
  }

  private async loadMapData(mapKey: string): Promise<{ features: GeoJSON.Feature[]; outline: GeoJSON.Feature } | null> {
    const cached = A2UIChart._mapCache.get(mapKey);
    if (cached) return cached;

    const src = A2UIChart.MAP_SOURCES[mapKey];
    if (!src) {
      console.warn(`[a2ui-chart] Unknown map key: "${mapKey}". Use "world" or "us-states".`);
      return null;
    }

    try {
      const resp = await fetch(src.url);
      const topo = (await resp.json()) as Topology;
      const featureCollection = topojson.feature(topo, topo.objects[src.featureKey]);
      const outlineCollection = topojson.feature(topo, topo.objects[src.outlineKey]);
      const features = (featureCollection as GeoJSON.FeatureCollection).features;
      const outline = (outlineCollection as GeoJSON.FeatureCollection).features?.[0]
        ?? (outlineCollection as unknown as GeoJSON.Feature);

      const result = { features, outline };
      A2UIChart._mapCache.set(mapKey, result);
      return result;
    } catch (err) {
      console.error(`[a2ui-chart] Failed to load map "${mapKey}":`, err);
      return null;
    }
  }

  private async renderGeoChart() {
    const ctx = this.canvas.getContext('2d');
    if (!ctx) return;

    const mapKey = this.data.map || 'world';
    this._geoLoading = true;
    const mapData = await this.loadMapData(mapKey);
    this._geoLoading = false;
    if (!mapData) return;

    const { features, outline } = mapData;
    const dataset = this.data.datasets[0];
    if (!dataset) return;

    const textSecondary = this.token('--a2ui-text-secondary') || '#9aa0a6';
    const bgApp = this.token('--a2ui-bg-app') || '#1a1a1a';
    const textPrimary = this.token('--a2ui-text-primary') || '#e3e3e3';
    const borderSubtle = this.token('--a2ui-border-subtle') || 'rgba(255,255,255,0.06)';
    const projection = mapKey === 'us-states' ? 'albersUsa' : 'equalEarth';

    if (this.chartType === 'choropleth') {
      const valueMap = new Map<string, number>();
      for (const d of dataset.data as Array<Record<string, unknown>>) {
        const name = String(d.feature ?? d.name ?? '');
        if (name && typeof d.value === 'number') {
          valueMap.set(name.toLowerCase(), d.value);
        }
      }

      const chartData = features.map(f => {
        const name = (f.properties?.name ?? '') as string;
        return { feature: f, value: valueMap.get(name.toLowerCase()) ?? 0 };
      });

      this.chart = new Chart(ctx, {
        type: 'choropleth' as any,
        data: {
          labels: features.map(f => (f.properties?.name ?? '') as string),
          datasets: [{
            label: dataset.label || '',
            outline,
            data: chartData,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              backgroundColor: bgApp,
              titleColor: textPrimary,
              bodyColor: textSecondary,
              borderColor: borderSubtle,
              borderWidth: 1,
              cornerRadius: 8,
              padding: { top: 8, bottom: 8, left: 12, right: 12 },
              titleFont: { family: 'Google Sans, Roboto, sans-serif', size: 12, weight: 'bold' as any },
              bodyFont: { family: 'Google Sans, Roboto, sans-serif', size: 11 },
            },
          },
          scales: {
            projection: { axis: 'x' as any, projection },
            color: {
              axis: 'x' as any,
              quantize: 5,
              legend: { position: 'bottom-right' as any, align: 'right' as any },
            },
          },
        },
      } as any);
    } else {
      // bubbleMap
      const chartData = (dataset.data as Array<Record<string, unknown>>).map(d => ({
        latitude: Number(d.latitude ?? d.lat ?? 0),
        longitude: Number(d.longitude ?? d.lng ?? d.lon ?? 0),
        value: Number(d.value ?? 0),
        description: String(d.description ?? d.label ?? ''),
      }));

      this.chart = new Chart(ctx, {
        type: 'bubbleMap' as any,
        data: {
          labels: chartData.map(d => d.description),
          datasets: [{
            label: dataset.label || '',
            outline,
            showOutline: true,
            backgroundColor: this.hexToRgba(this.palette[0], 0.65),
            data: chartData,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              backgroundColor: bgApp,
              titleColor: textPrimary,
              bodyColor: textSecondary,
              borderColor: borderSubtle,
              borderWidth: 1,
              cornerRadius: 8,
              padding: { top: 8, bottom: 8, left: 12, right: 12 },
              titleFont: { family: 'Google Sans, Roboto, sans-serif', size: 12, weight: 'bold' as any },
              bodyFont: { family: 'Google Sans, Roboto, sans-serif', size: 11 },
            },
          },
          scales: {
            projection: { axis: 'x' as any, projection },
            size: { axis: 'x' as any, size: [1, 20] },
          },
        },
      } as any);
    }
  }

  private renderChart() {
    if (!this.canvas) return;

    this.chart?.destroy();

    const isGeo = this.chartType === 'choropleth' || this.chartType === 'bubbleMap';
    if (isGeo) {
      this.renderGeoChart();
      return;
    }

    const scatterFixed = this.normalizeScatterData();
    const chartData = scatterFixed !== this.data ? scatterFixed : this.normalizeMatrixData();

    const ctx = this.canvas.getContext('2d');
    if (!ctx) return;

    // Resolve theme-aware colors from tokens
    const textSecondary = this.token('--a2ui-text-secondary') || '#9aa0a6';
    const textTertiary = this.token('--a2ui-text-tertiary') || '#71767b';
    const textPrimary = this.token('--a2ui-text-primary') || '#e3e3e3';
    const bgApp = this.token('--a2ui-bg-app') || '#1a1a1a';
    const borderSubtle = this.token('--a2ui-border-subtle') || 'rgba(255,255,255,0.06)';

    const isLine = this.chartType === 'line';
    const isBar = this.chartType === 'bar';
    const isPie = this.chartType === 'pie' || this.chartType === 'doughnut';
    const isRadar = this.chartType === 'radar';
    const isPolar = this.chartType === 'polarArea';
    const isScatter = this.chartType === 'scatter';
    const isBubble = this.chartType === 'bubble';
    const isTreemap = this.chartType === 'treemap';
    const isSankey = this.chartType === 'sankey';
    const isFunnel = this.chartType === 'funnel';
    const isMatrix = this.chartType === 'matrix';
    const isRadial = isRadar || isPolar;
    const isPointBased = isScatter || isBubble;
    const isPlugin = isTreemap || isSankey || isFunnel || isMatrix;
    // geo types handled by renderGeoChart() above — won't reach here
    const isSingleDataset = chartData.datasets.length === 1;
    const chartHeight = this.options.height || 240;

    const shouldFill = isLine && (this.options.fillArea !== undefined ? this.options.fillArea : isSingleDataset);
    const showGrid = this.options.showGrid !== undefined ? this.options.showGrid : (isBar || isRadial);
    const showLegend = this.options.showLegend !== undefined
      ? this.options.showLegend
      : (isPie || isPolar || chartData.datasets.length > 1);

    const palette = this.palette;
    const datasets = chartData.datasets.map((ds, i) => {
      const color = (ds.borderColor as string) || this.getColor(i);
      const labelsLen = chartData.labels?.length ?? 0;

      if (isTreemap) {
        return {
          ...ds,
          borderColor: this.token('--a2ui-border-subtle') || 'rgba(255,255,255,0.15)',
          borderWidth: 2,
          spacing: 2,
          backgroundColor: (ctx: unknown) => {
            const c = ctx as { dataIndex?: number };
            return palette[(c.dataIndex ?? 0) % palette.length] + 'CC';
          },
          labels: {
            display: true,
            align: 'center' as const,
            position: 'middle' as const,
            color: textPrimary,
            font: { family: 'Google Sans, Roboto, sans-serif', size: 12, weight: 'bold' as const },
            formatter: (ctx: unknown) => {
              const c = ctx as { raw?: { _data?: { label?: string; group?: string }; v?: number } };
              return c.raw?._data?.label || c.raw?._data?.group || '';
            },
          },
        };
      }

      if (isMatrix) {
        const allData = ds.data as Array<{ x: number | string; y: number | string; v: number }>;
        const values = allData.map(d => d.v ?? 0);
        const minV = Math.min(...values);
        const maxV = Math.max(...values);
        const range = maxV - minV || 1;

        return {
          ...ds,
          borderColor: this.token('--a2ui-border-subtle') || 'rgba(255,255,255,0.08)',
          borderWidth: 1,
          borderRadius: 2,
          width: ({ chart }: { chart: Chart }) => {
            const xLabels = chart.scales?.x?.ticks?.length || 1;
            return (chart.chartArea?.width || 200) / xLabels - 2;
          },
          height: ({ chart }: { chart: Chart }) => {
            const yLabels = chart.scales?.y?.ticks?.length || 1;
            return (chart.chartArea?.height || 200) / yLabels - 2;
          },
          backgroundColor: (ctx: unknown) => {
            const c = ctx as { raw?: { v?: number } };
            const v = c.raw?.v ?? 0;
            const t = (v - minV) / range;
            // Cool-to-warm gradient: blue (#8ab4f8) → yellow (#fdd663) → red (#f28b82)
            const r = Math.round(t < 0.5 ? 138 + t * 2 * (253 - 138) : 253 - (t - 0.5) * 2 * (253 - 242));
            const g = Math.round(t < 0.5 ? 180 + t * 2 * (214 - 180) : 214 - (t - 0.5) * 2 * (214 - 139));
            const b = Math.round(t < 0.5 ? 248 - t * 2 * (248 - 99) : 99 + (t - 0.5) * 2 * (130 - 99));
            return `rgba(${r}, ${g}, ${b}, 0.85)`;
          },
        };
      }

      if (isSankey || isFunnel) {
        return {
          ...ds,
          borderColor: ds.borderColor || color,
          backgroundColor: ds.backgroundColor || this.hexToRgba(color, 0.7),
          borderWidth: ds.borderWidth ?? 1,
          ...(isSankey ? {
            colorFrom: (ctx: unknown) => {
              const c = ctx as { dataIndex?: number };
              return palette[(c.dataIndex ?? 0) % palette.length] + 'CC';
            },
            colorTo: (ctx: unknown) => {
              const c = ctx as { dataIndex?: number };
              return palette[((c.dataIndex ?? 0) + 1) % palette.length] + 'CC';
            },
          } : {}),
        };
      }

      let bgColor: string | string[] | CanvasGradient;
      if (ds.backgroundColor) {
        bgColor = ds.backgroundColor;
      } else if (isLine) {
        bgColor = shouldFill ? this.createGradient(ctx, color, chartHeight) : 'transparent';
      } else if (isPie || isPolar) {
        bgColor = this.palette.slice(0, labelsLen).map(c => this.hexToRgba(c, 0.7));
      } else if (isRadar) {
        bgColor = this.hexToRgba(color, 0.15);
      } else if (isScatter || isBubble) {
        bgColor = this.hexToRgba(color, 0.6);
      } else {
        bgColor = this.hexToRgba(color, 0.7);
      }

      return {
        ...ds,
        borderColor: color,
        backgroundColor: bgColor,
        borderWidth: ds.borderWidth ?? (isLine || isRadar ? 2.5 : isScatter || isBubble ? 1 : 0),
        tension: isLine ? 0.35 : undefined,
        fill: isLine ? shouldFill : (isRadar ? true : undefined),
        pointRadius: isLine ? 0 : (isRadar ? 3 : (isScatter ? 4 : undefined)),
        pointHoverRadius: isLine || isRadar ? 5 : (isScatter ? 6 : undefined),
        pointHoverBackgroundColor: (isLine || isRadar || isScatter) ? color : undefined,
        pointHoverBorderColor: (isLine || isRadar || isScatter) ? bgApp : undefined,
        pointHoverBorderWidth: (isLine || isRadar || isScatter) ? 2 : undefined,
        borderRadius: isBar ? 4 : undefined,
        maxBarThickness: isBar ? 48 : undefined,
      };
    });

    const self = this;

    const config: ChartConfiguration = {
      type: this.chartType,
      data: {
        ...(chartData.labels ? { labels: chartData.labels } : {}),
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
              color: textSecondary,
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
            backgroundColor: bgApp,
            titleColor: textPrimary,
            bodyColor: textSecondary,
            borderColor: borderSubtle,
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
            displayColors: chartData.datasets.length > 1,
            boxWidth: 8,
            boxHeight: 8,
            boxPadding: 4,
            usePointStyle: true,
            callbacks: {
              label(context: TooltipItem<'bar'>) {
                const label = context.dataset.label || '';
                const raw = context.raw;

                // Matrix/heatmap: raw has v for value
                if (raw && typeof raw === 'object' && 'v' in raw) {
                  const pt = raw as { x: string | number; y: string | number; v: number };
                  const value = self.formatValue(pt.v);
                  return `${pt.y} × ${pt.x}: ${value}`;
                }

                // Radar/polar: raw is just a number
                if (typeof raw === 'number') {
                  const value = self.formatValue(raw);
                  return label ? `${label}: ${value}` : value;
                }

                // Scatter/bubble: raw is {x, y, r?}
                if (raw && typeof raw === 'object' && 'x' in raw && 'y' in raw) {
                  const pt = raw as { x: number; y: number; r?: number };
                  const x = self.formatValue(pt.x);
                  const y = self.formatValue(pt.y);
                  const rStr = pt.r !== undefined ? `, size: ${pt.r}` : '';
                  return label ? `${label}: (${x}, ${y}${rStr})` : `(${x}, ${y}${rStr})`;
                }

                // Bar/line/pie: parsed.y or raw number
                const parsed = context.parsed as unknown as Record<string, number>;
                const value = self.formatValue(parsed.y ?? (raw as number));
                return label ? `${label}: ${value}` : value;
              },
            },
          },
          // Pass reference line config via plugin options
          a2uiReferenceLine: this.options.referenceLine
            ? { value: this.options.referenceLine, label: this.options.referenceLabel }
            : undefined,
        } as Record<string, unknown>,
        scales: isMatrix ? {
          x: {
            type: 'category' as const,
            offset: true,
            grid: { display: false },
            border: { display: false },
            ticks: {
              color: textTertiary,
              font: { family: 'Google Sans, Roboto, sans-serif', size: 10 },
              maxRotation: 45,
            },
            ...(this.options.xAxisLabel ? {
              title: {
                display: true,
                text: this.options.xAxisLabel,
                color: textSecondary,
                font: { family: 'Google Sans, Roboto, sans-serif', size: 11, weight: 'bold' as const },
                padding: { top: 8 },
              },
            } : {}),
          },
          y: {
            type: 'category' as const,
            labels: this._matrixRows,
            offset: true,
            grid: { display: false },
            border: { display: false },
            ticks: {
              color: textTertiary,
              font: { family: 'Google Sans, Roboto, sans-serif', size: 10 },
            },
            ...(this.options.yAxisLabel ? {
              title: {
                display: true,
                text: this.options.yAxisLabel,
                color: textSecondary,
                font: { family: 'Google Sans, Roboto, sans-serif', size: 11, weight: 'bold' as const },
                padding: { bottom: 8 },
              },
            } : {}),
          },
        } : ((isPlugin && !isMatrix) || isPie) ? undefined : isRadial ? {
          r: {
            grid: { color: borderSubtle },
            angleLines: { color: borderSubtle },
            pointLabels: {
              color: textSecondary,
              font: { family: 'Google Sans, Roboto, sans-serif', size: 11 },
            },
            ticks: {
              color: textTertiary,
              backdropColor: 'transparent',
              font: { family: 'Google Sans, Roboto, sans-serif', size: 9 },
            },
          },
        } : {
          x: {
            grid: {
              display: showGrid,
              color: borderSubtle,
              drawTicks: false,
            },
            border: {
              display: false,
            },
            ...(this.options.xAxisLabel ? {
              title: {
                display: true,
                text: this.options.xAxisLabel,
                color: textSecondary,
                font: {
                  family: 'Google Sans, Roboto, sans-serif',
                  size: 11,
                  weight: '500' as const,
                },
                padding: { top: 8 },
              },
            } : {}),
            ticks: {
              color: textTertiary,
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
              color: borderSubtle,
              drawTicks: false,
            },
            border: {
              display: false,
            },
            ...(this.options.yAxisLabel ? {
              title: {
                display: true,
                text: this.options.yAxisLabel,
                color: textSecondary,
                font: {
                  family: 'Google Sans, Roboto, sans-serif',
                  size: 11,
                  weight: '500' as const,
                },
                padding: { bottom: 8 },
              },
            } : {}),
            ticks: {
              color: textTertiary,
              padding: 8,
              font: {
                family: 'Google Sans, Roboto, sans-serif',
                size: 10,
              },
              callback: (value: string | number) => self.formatValue(Number(value)),
            },
          },
        },
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
          ${this._geoLoading ? html`
            <div class="geo-loading" style="height: ${height}px">
              <div class="spinner"></div>
              <span>Loading map…</span>
            </div>
          ` : ''}
          <canvas style="${this._geoLoading ? 'display:none' : ''}"></canvas>
        </div>
      </div>
    `;
  }
}
