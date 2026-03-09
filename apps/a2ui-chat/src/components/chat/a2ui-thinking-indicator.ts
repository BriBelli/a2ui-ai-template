import { LitElement, html, css, nothing } from "lit";
import { customElement, property, state } from "lit/decorators.js";
import type { LoadingDetail, LoadingStyle } from "../../config/ui-config";

export interface ThinkingStep {
  label: string;
  done: boolean;
  detail?: string;
  /** Backend tool identifier (e.g. "analyzer", "search", "llm"). */
  tool?: string;
  /** Chain-of-thought reasoning prose (shown in 'thought' detail mode). */
  reasoning?: string;
}

/** Maps backend step IDs to the minimum detail level required to see them. */
const STEP_VISIBILITY: Record<string, LoadingDetail[]> = {
  tools: ["comprehensive", "thought"],
  analyzer: ["comprehensive", "moderate", "thought"],
  search: ["comprehensive", "moderate", "thought"],
  "data-sources": ["comprehensive", "moderate", "thought"],
  location: ["comprehensive", "moderate", "thought"],
  model_upgrade: ["comprehensive", "moderate", "thought"],
  llm: ["comprehensive", "moderate", "thought"],
};

function isStepVisible(
  toolId: string | undefined,
  level: LoadingDetail,
): boolean {
  if (!toolId) return level !== "basic";
  const allowed = STEP_VISIBILITY[toolId];
  return allowed ? allowed.includes(level) : level !== "basic";
}

const STEP_HEIGHT_COMPACT = 22;
const STEP_HEIGHT_DETAIL = 36;

@customElement("a2ui-thinking-indicator")
export class A2UIThinkingIndicator extends LitElement {
  static styles = css`
    :host {
      display: block;
    }

    .thinking {
      display: flex;
      align-items: flex-start;
      gap: var(--a2ui-space-3);
      padding: var(--a2ui-space-4) 0;
    }

    .avatar {
      width: 32px;
      height: 32px;
      border-radius: var(--a2ui-radius-full);
      background: conic-gradient(
        from 180deg,
        rgb(242, 139, 130),
        rgb(253, 214, 99),
        rgb(129, 201, 149),
        rgb(138, 180, 248),
        rgb(197, 138, 249),
        rgb(242, 139, 130)
      );
      display: flex;
      align-items: center;
      justify-content: center;
      color: white;
      font-size: var(--a2ui-text-sm);
      font-weight: var(--a2ui-font-medium);
      flex-shrink: 0;
    }

    .content {
      display: flex;
      flex-direction: column;
      gap: var(--a2ui-space-2);
      min-width: 0;
    }

    .header {
      display: flex;
      align-items: center;
      gap: var(--a2ui-space-2);
      color: var(--a2ui-text-secondary);
      font-size: var(--a2ui-text-sm);
    }

    .elapsed {
      color: var(--a2ui-text-tertiary);
      font-size: var(--a2ui-text-xs);
      margin-left: auto;
      font-variant-numeric: tabular-nums;
    }

    .spinner {
      width: 14px;
      height: 14px;
      border: 2px solid var(--a2ui-border-default);
      border-top-color: var(--a2ui-accent);
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }

    @keyframes spin {
      to {
        transform: rotate(360deg);
      }
    }

    /* ── Shared step styles ──────────────────────────── */

    .step {
      display: flex;
      align-items: flex-start;
      gap: var(--a2ui-space-2);
      font-size: var(--a2ui-text-xs);
      box-sizing: border-box;
      padding: 3px 0;
      color: var(--a2ui-text-secondary);
      transition:
        opacity 0.3s ease,
        color 0.3s ease;
    }

    .step.done {
      opacity: 0.45;
      color: var(--a2ui-text-tertiary);
    }

    .step-icon {
      width: 14px;
      height: 14px;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      margin-top: 1px;
    }

    .step-icon svg {
      width: 12px;
      height: 12px;
    }

    .check {
      color: var(--a2ui-success);
    }

    .step-spinner {
      width: 10px;
      height: 10px;
      border: 1.5px solid var(--a2ui-border-default);
      border-top-color: var(--a2ui-text-tertiary);
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }

    .step-text {
      display: flex;
      flex-direction: column;
      gap: 1px;
      min-width: 0;
    }

    .step-label {
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .step-detail {
      color: var(--a2ui-accent);
      font-size: 10px;
      font-style: italic;
      opacity: 0.85;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    /* ── Style: basic ────────────────────────────────── */

    .steps-basic {
      display: flex;
      flex-direction: column;
      gap: 2px;
      padding-left: var(--a2ui-space-1);
    }

    .steps-basic .step {
      opacity: 0;
      animation: basicFadeIn 0.25s ease forwards;
    }

    .steps-basic .step.done {
      animation: none;
      opacity: 0.45;
    }

    @keyframes basicFadeIn {
      from {
        opacity: 0;
      }
      to {
        opacity: 1;
      }
    }

    /* ── Style: focus (slot machine) ─────────────────── */

    .steps-focus {
      overflow: hidden;
      position: relative;
      padding-left: var(--a2ui-space-1);
    }

    .steps-focus-reel {
      display: flex;
      flex-direction: column;
      transition: transform 0.45s cubic-bezier(0.22, 1, 0.36, 1);
    }

    .steps-focus .step {
      flex-shrink: 0;
      height: var(--focus-step-h);
      opacity: 0.35;
      transition:
        opacity 0.3s ease,
        color 0.3s ease;
    }

    .steps-focus .step.current {
      opacity: 1;
    }

    /* ── Style: stack ────────────────────────────────── */

    .steps-stack {
      display: flex;
      flex-direction: column;
      gap: 2px;
      padding-left: var(--a2ui-space-1);
      max-height: 160px;
      overflow-y: auto;
      scrollbar-width: thin;
      scrollbar-color: var(--a2ui-border-default) transparent;
    }

    .steps-stack::-webkit-scrollbar {
      width: 4px;
    }

    .steps-stack::-webkit-scrollbar-track {
      background: transparent;
    }

    .steps-stack::-webkit-scrollbar-thumb {
      background: var(--a2ui-border-default);
      border-radius: 2px;
    }

    .steps-stack .step {
      flex-shrink: 0;
      opacity: 0;
      transform: translateY(4px);
      animation: stackSlideIn 0.3s ease forwards;
    }

    .steps-stack .step.done {
      animation: none;
      opacity: 0.45;
      transform: none;
    }

    @keyframes stackSlideIn {
      from {
        opacity: 0;
        transform: translateY(4px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }

    /* ── Thought panel (chain-of-thought) ────────────── */

    .thought-panel {
      margin-top: var(--a2ui-space-1);
      border-left: 2px solid var(--a2ui-border-subtle);
      padding-left: var(--a2ui-space-3);
    }

    .thought-toggle {
      display: flex;
      align-items: center;
      gap: var(--a2ui-space-1);
      background: none;
      border: none;
      padding: var(--a2ui-space-1) 0;
      color: var(--a2ui-text-tertiary);
      font-family: var(--a2ui-font-family);
      font-size: var(--a2ui-text-xs);
      font-weight: var(--a2ui-font-medium);
      cursor: pointer;
      transition: color 0.15s ease;
    }

    .thought-toggle:hover {
      color: var(--a2ui-text-secondary);
    }

    .thought-chevron {
      display: inline-block;
      width: 10px;
      height: 10px;
      transition: transform 0.2s ease;
    }

    .thought-chevron.open {
      transform: rotate(90deg);
    }

    .thought-body {
      max-height: 200px;
      overflow-y: auto;
      scrollbar-width: thin;
      scrollbar-color: var(--a2ui-border-default) transparent;
      padding: var(--a2ui-space-1) 0;
      animation: thoughtFadeIn 0.2s ease forwards;
    }

    .thought-body::-webkit-scrollbar {
      width: 4px;
    }

    .thought-body::-webkit-scrollbar-thumb {
      background: var(--a2ui-border-default);
      border-radius: 2px;
    }

    @keyframes thoughtFadeIn {
      from {
        opacity: 0;
      }
      to {
        opacity: 1;
      }
    }

    .thought-entry {
      font-size: 11px;
      line-height: 1.5;
      color: var(--a2ui-text-tertiary);
      padding: 2px 0;
      border-bottom: 1px solid var(--a2ui-border-subtle);
    }

    .thought-entry:last-child {
      border-bottom: none;
    }

    .thought-entry-label {
      color: var(--a2ui-text-secondary);
      font-weight: var(--a2ui-font-medium);
      margin-right: var(--a2ui-space-1);
    }

    .thought-entry.latest {
      color: var(--a2ui-text-secondary);
    }
  `;

  @property({ type: Array }) steps: ThinkingStep[] = [];
  @property({ type: String }) detailLevel: LoadingDetail = "moderate";
  @property({ type: String }) styleMode: LoadingStyle = "focus";

  @state() private elapsed = 0;
  @state() private _thoughtOpen = true;
  private _timer = 0;

  private get _focusStepHeight(): number {
    return this.detailLevel === "comprehensive" ||
      this.detailLevel === "thought"
      ? STEP_HEIGHT_DETAIL
      : STEP_HEIGHT_COMPACT;
  }

  connectedCallback() {
    super.connectedCallback();
    this.elapsed = 0;
    this._timer = window.setInterval(() => {
      this.elapsed++;
    }, 1000);
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    clearInterval(this._timer);
  }

  updated(changed: Map<string, unknown>) {
    if (changed.has("steps")) {
      if (this.styleMode === "stack") {
        const el = this.renderRoot.querySelector(".steps-stack");
        if (el)
          requestAnimationFrame(() => {
            el.scrollTop = el.scrollHeight;
          });
      }
      if (this.detailLevel === "thought") {
        const el = this.renderRoot.querySelector(".thought-body");
        if (el)
          requestAnimationFrame(() => {
            el.scrollTop = el.scrollHeight;
          });
      }
    }
  }

  private _renderStepIcon(done: boolean) {
    if (done) {
      return html`
        <span class="step-icon check">
          <svg viewBox="0 0 24 24" fill="currentColor">
            <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" />
          </svg>
        </span>
      `;
    }
    return html`<span class="step-icon"
      ><span class="step-spinner"></span
    ></span>`;
  }

  private _getVisibleSteps(): ThinkingStep[] {
    if (this.detailLevel === "basic") return [];
    return this.steps.filter((s) => isStepVisible(s.tool, this.detailLevel));
  }

  private _renderStep(step: ThinkingStep, extraClass = "") {
    const showDetail =
      this.detailLevel === "comprehensive" || this.detailLevel === "thought";
    return html`
      <div class="step ${step.done ? "done" : ""} ${extraClass}">
        ${this._renderStepIcon(step.done)}
        <span class="step-text">
          <span class="step-label">${step.label}</span>
          ${showDetail && step.detail
            ? html`<span class="step-detail">${step.detail}</span>`
            : nothing}
        </span>
      </div>
    `;
  }

  /** Basic: simple list, steps fade in and stay */
  private _renderBasic(steps: ThinkingStep[]) {
    return html`
      <div class="steps-basic">${steps.map((s) => this._renderStep(s))}</div>
    `;
  }

  /** Focus: slot machine — one active step visible at a time */
  private _renderFocus(steps: ThinkingStep[]) {
    let activeIdx = steps.length - 1;
    for (let i = steps.length - 1; i >= 0; i--) {
      if (!steps[i].done) {
        activeIdx = i;
        break;
      }
    }
    const h = this._focusStepHeight;
    const offset = -activeIdx * h;

    return html`
      <div class="steps-focus" style="height: ${h}px; --focus-step-h: ${h}px">
        <div
          class="steps-focus-reel"
          style="transform: translateY(${offset}px)"
        >
          ${steps.map((s, i) =>
            this._renderStep(s, i === activeIdx ? "current" : ""),
          )}
        </div>
      </div>
    `;
  }

  /** Stack: all steps visible, scrollable */
  private _renderStack(steps: ThinkingStep[]) {
    return html`
      <div class="steps-stack">${steps.map((s) => this._renderStep(s))}</div>
    `;
  }

  /** Collapsible chain-of-thought reasoning panel */
  private _renderThoughtPanel(steps: ThinkingStep[]) {
    const entries = steps
      .filter((s) => s.reasoning)
      .map((s, _i, arr) => ({
        label: s.label,
        reasoning: s.reasoning!,
        done: s.done,
        latest: s === arr[arr.length - 1],
      }));

    if (entries.length === 0) return nothing;

    const chevronSvg = html`
      <svg
        class="thought-chevron ${this._thoughtOpen ? "open" : ""}"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2.5"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <polyline points="9 18 15 12 9 6" />
      </svg>
    `;

    return html`
      <div class="thought-panel">
        <button
          class="thought-toggle"
          @click=${() => {
            this._thoughtOpen = !this._thoughtOpen;
          }}
        >
          ${chevronSvg} Reasoning (${entries.length})
        </button>
        ${this._thoughtOpen
          ? html`
              <div class="thought-body">
                ${entries.map(
                  (e) => html`
                    <div class="thought-entry ${e.latest ? "latest" : ""}">
                      <span class="thought-entry-label">${e.label}:</span>
                      ${e.reasoning}
                    </div>
                  `,
                )}
              </div>
            `
          : nothing}
      </div>
    `;
  }

  render() {
    const visibleSteps = this._getVisibleSteps();
    const isThought = this.detailLevel === "thought";

    const stepsHtml =
      visibleSteps.length > 0
        ? this.styleMode === "focus"
          ? this._renderFocus(visibleSteps)
          : this.styleMode === "stack"
            ? this._renderStack(visibleSteps)
            : this._renderBasic(visibleSteps)
        : nothing;

    return html`
      <div class="thinking">
        <div class="avatar">AI</div>
        <div class="content">
          <div class="header">
            <span class="spinner"></span>
            <span>Thinking...</span>
            ${this.elapsed >= 2
              ? html`<span class="elapsed">${this.elapsed}s</span>`
              : nothing}
          </div>
          ${stepsHtml}
          ${isThought ? this._renderThoughtPanel(this.steps) : nothing}
        </div>
      </div>
    `;
  }
}
