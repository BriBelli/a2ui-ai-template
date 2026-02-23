import { LitElement, html, css, unsafeCSS, nothing } from "lit";
import { customElement, property, state } from "lit/decorators.js";
import type { ChatMessage, SourceCitation } from "../../services/chat-service";
import { A2UIRenderer } from "../../services/a2ui-renderer";
import { uiConfig } from "../../config/ui-config";
import { md, markdownStyles, renderMermaidDiagrams } from "../../services/markdown";

@customElement("a2ui-chat-message")
export class A2UIChatMessage extends LitElement {
  static styles = css`
    :host {
      display: block;
      margin-bottom: var(--a2ui-space-4);
    }

    /* Message entrance animation (when enabled) */
    :host([animate]) {
      animation: messageIn 0.3s cubic-bezier(0.22, 1, 0.36, 1) forwards;
      opacity: 0;
    }

    @keyframes messageIn {
      from {
        opacity: 0;
        transform: translateY(12px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }

    .message {
      display: flex;
      gap: var(--a2ui-space-3);
    }

    .message.user {
      flex-direction: row-reverse;
    }

    .avatar {
      width: 32px;
      height: 32px;
      border-radius: var(--a2ui-radius-full);
      flex-shrink: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: var(--a2ui-text-sm);
      font-weight: var(--a2ui-font-medium);
      transition: transform 0.2s ease;
    }

    .avatar:hover {
      transform: scale(1.05);
    }

    .avatar.user {
      background: var(--a2ui-accent);
      color: var(--a2ui-text-inverse);
      overflow: hidden;
    }

    .avatar.user img {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }

    .avatar.assistant {
      background: linear-gradient(135deg, #4285f4, #ea4335, #fbbc05, #34a853);
      color: white;
    }

    .content {
      flex: 1;
      min-width: 0;
    }

    .user .content {
      display: flex;
      flex-direction: column;
      align-items: flex-end;
    }

    .bubble {
      max-width: 100%;
    }

    .user .bubble {
      padding: var(--a2ui-space-3) var(--a2ui-space-4);
      background: var(--a2ui-accent);
      color: var(--a2ui-text-inverse);
      border-radius: var(--a2ui-radius-xl);
      border-bottom-right-radius: var(--a2ui-radius-sm);
      transition: box-shadow 0.15s ease;
    }

    .user .bubble:hover {
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
    }

    .assistant .bubble {
      color: var(--a2ui-text-primary);
    }

    .text-content {
      white-space: pre-wrap;
      word-break: break-word;
      line-height: var(--a2ui-leading-relaxed);
    }

    .assistant .text-content {
      white-space: normal;
      padding: var(--a2ui-space-1) 0;
    }

    .a2ui-content {
      margin-top: var(--a2ui-space-3);
    }

    /* A2UI content fade-in (when animated) */
    :host([animate]) .a2ui-content {
      animation: contentFadeIn 0.4s ease 0.15s forwards;
      opacity: 0;
    }

    @keyframes contentFadeIn {
      from {
        opacity: 0;
      }
      to {
        opacity: 1;
      }
    }

    .meta {
      display: flex;
      align-items: center;
      gap: var(--a2ui-space-2);
      margin-top: var(--a2ui-space-1);
      font-size: var(--a2ui-text-xs);
      color: var(--a2ui-text-tertiary);
    }

    /* Meta fade-in (when animated) */
    :host([animate]) .meta {
      animation: metaFadeIn 0.3s ease 0.2s forwards;
      opacity: 0;
    }

    @keyframes metaFadeIn {
      from {
        opacity: 0;
      }
      to {
        opacity: 1;
      }
    }

    .user .meta {
      justify-content: flex-end;
    }

    .model-badge {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 2px 6px;
      background: var(--a2ui-bg-tertiary);
      border-radius: var(--a2ui-radius-sm);
      font-size: 10px;
      transition: background-color 0.15s ease;
    }

    .model-badge:hover {
      background: var(--a2ui-bg-elevated);
    }

    .model-badge .wand-icon {
      width: 12px;
      height: 12px;
      flex-shrink: 0;
    }

    .model-badge .provider-icon {
      width: 12px;
      height: 12px;
      flex-shrink: 0;
      border-radius: 2px;
    }

    .duration,
    .style-badge {
      text-transform: capitalize;
      color: var(--a2ui-text-tertiary);
    }

    /* ── Edit mode ────────────────────────────────────── */

    .user .bubble {
      cursor: default;
    }

    .user .bubble.editable {
      cursor: pointer;
    }

    .edit-container {
      display: flex;
      flex-direction: column;
      gap: var(--a2ui-space-2);
      width: 100%;
      max-width: 600px;
    }

    .edit-textarea {
      width: 100%;
      min-height: 60px;
      max-height: 200px;
      padding: var(--a2ui-space-3) var(--a2ui-space-4);
      background: var(--a2ui-bg-primary);
      color: var(--a2ui-text-primary);
      border: 1.5px solid var(--a2ui-accent);
      border-radius: var(--a2ui-radius-xl);
      border-bottom-right-radius: var(--a2ui-radius-sm);
      font-family: var(--a2ui-font-family);
      font-size: var(--a2ui-text-base);
      line-height: var(--a2ui-leading-relaxed);
      resize: vertical;
      outline: none;
      box-sizing: border-box;
      transition:
        border-color 0.15s ease,
        box-shadow 0.15s ease;
    }

    .edit-textarea:focus {
      box-shadow: 0 0 0 3px rgba(66, 133, 244, 0.15);
    }

    .edit-actions {
      display: flex;
      gap: var(--a2ui-space-2);
      justify-content: flex-end;
    }

    .edit-btn {
      padding: var(--a2ui-space-1) var(--a2ui-space-3);
      border-radius: var(--a2ui-radius-md);
      border: none;
      font-family: var(--a2ui-font-family);
      font-size: var(--a2ui-text-sm);
      font-weight: var(--a2ui-font-medium);
      cursor: pointer;
      transition:
        background 0.15s ease,
        opacity 0.15s ease;
    }

    .edit-btn.cancel {
      background: var(--a2ui-bg-tertiary);
      color: var(--a2ui-text-secondary);
    }

    .edit-btn.cancel:hover {
      background: var(--a2ui-bg-elevated);
    }

    .edit-btn.submit {
      background: var(--a2ui-accent);
      color: var(--a2ui-text-inverse);
    }

    .edit-btn.submit:hover {
      opacity: 0.9;
    }

    .edit-btn.submit:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }

    /* ── Image strip ──────────────────────────────────── */

    .image-strip {
      display: flex;
      gap: var(--a2ui-space-2);
      margin-top: var(--a2ui-space-3);
      overflow-x: auto;
      padding-bottom: var(--a2ui-space-1);
      scrollbar-width: thin;
    }

    .image-strip::-webkit-scrollbar {
      height: 4px;
    }

    .image-strip::-webkit-scrollbar-track {
      background: transparent;
    }

    .image-strip::-webkit-scrollbar-thumb {
      background: var(--a2ui-border-default);
      border-radius: 2px;
    }

    .image-strip a {
      flex-shrink: 0;
      display: block;
      width: 160px;
      height: 110px;
      border-radius: var(--a2ui-radius-md);
      overflow: hidden;
      background: var(--a2ui-bg-tertiary);
      transition:
        opacity var(--a2ui-transition-fast),
        transform var(--a2ui-transition-fast);
    }

    .image-strip a:hover {
      opacity: 0.85;
      transform: scale(1.02);
    }

    .image-strip img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
    }

    /* ── Two-column layout (content + sources) ────────── */

    .content {
      container-type: inline-size;
    }

    .response-layout {
      display: flex;
      flex-wrap: wrap;
      gap: var(--a2ui-space-6);
    }

    .response-main {
      flex: 1;
      min-width: 0;
    }

    .sources-panel {
      flex-shrink: 0;
      width: 280px;
      align-self: flex-start;
      position: sticky;
      top: var(--a2ui-space-4);
    }

    /* Position: bottom — always stacked */
    .response-layout.pos-bottom {
      flex-direction: column;
      gap: var(--a2ui-space-4);
    }

    .response-layout.pos-bottom .sources-panel {
      width: 100%;
      position: static;
      order: 1;
    }

    .response-layout.pos-bottom .response-main {
      order: 2;
    }

    .response-layout.pos-bottom .followups {
      order: 3;
    }

    .response-layout.pos-bottom .sources-list {
      flex-direction: row;
      overflow-x: auto;
      gap: var(--a2ui-space-3);
      padding-bottom: var(--a2ui-space-1);
      scrollbar-width: thin;
    }

    .response-layout.pos-bottom .source-card {
      flex-direction: column;
      width: 200px;
      flex-shrink: 0;
      border-bottom: none;
      padding: var(--a2ui-space-2);
      background: var(--a2ui-bg-secondary);
      border-radius: var(--a2ui-radius-lg);
    }

    .response-layout.pos-bottom .source-thumb,
    .response-layout.pos-bottom .source-favicon-wrap,
    .response-layout.pos-bottom .source-data-icon {
      width: 100%;
      height: 100px;
    }

    /* ── Sources panel ─────────────────────────────────── */

    .sources-header {
      display: flex;
      align-items: center;
      gap: var(--a2ui-space-2);
      padding-bottom: var(--a2ui-space-2);
      margin-bottom: var(--a2ui-space-2);
      border-bottom: 1px solid var(--a2ui-border-subtle);
      color: var(--a2ui-text-tertiary);
      font-size: var(--a2ui-text-xs);
      font-weight: var(--a2ui-font-medium);
    }

    .sources-header svg {
      width: 14px;
      height: 14px;
      flex-shrink: 0;
    }

    .sources-count {
      font-weight: var(--a2ui-font-semibold);
    }

    .sources-list {
      display: flex;
      flex-direction: column;
      gap: var(--a2ui-space-2);
    }

    .source-card {
      display: flex;
      align-items: flex-start;
      gap: var(--a2ui-space-3);
      padding: var(--a2ui-space-2) 0;
      text-decoration: none;
      border-bottom: 1px solid var(--a2ui-border-subtle);
      transition: opacity 0.12s ease;
    }

    .source-card:last-child {
      border-bottom: none;
    }

    .source-card:hover {
      opacity: 0.8;
    }

    .source-thumb {
      width: 72px;
      height: 72px;
      border-radius: var(--a2ui-radius-md);
      background: var(--a2ui-bg-tertiary);
      flex-shrink: 0;
      overflow: hidden;
    }

    .source-thumb img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
    }

    .source-favicon-wrap {
      width: 50px;
      height: 50px;
      border-radius: var(--a2ui-radius-md);
      background: var(--a2ui-bg-tertiary);
      flex-shrink: 0;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .source-favicon {
      width: 24px;
      height: 24px;
      border-radius: var(--a2ui-radius-sm);
      object-fit: contain;
    }

    .source-info {
      flex: 1;
      min-width: 0;
      padding-top: 2px;
    }

    .source-title {
      font-size: var(--a2ui-text-sm);
      font-weight: var(--a2ui-font-medium);
      color: var(--a2ui-text-primary);
      line-height: 1.3;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
      margin-bottom: 2px;
    }

    .source-desc {
      font-size: var(--a2ui-text-xs);
      color: var(--a2ui-text-secondary);
      line-height: 1.4;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
      margin-bottom: 4px;
    }

    .source-meta {
      display: flex;
      align-items: center;
      gap: var(--a2ui-space-1);
      font-size: 10px;
      color: var(--a2ui-text-tertiary);
    }

    .source-meta-icon {
      width: 14px;
      height: 14px;
      border-radius: 50%;
      object-fit: contain;
    }

    .source-domain {
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .source-data-icon {
      width: 50px;
      height: 50px;
      border-radius: var(--a2ui-radius-md);
      background: var(--a2ui-bg-tertiary);
      color: var(--a2ui-text-tertiary);
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }

    .source-data-icon svg {
      width: 24px;
      height: 24px;
    }

    .sources-show-all {
      display: flex;
      align-items: center;
      justify-content: center;
      padding: var(--a2ui-space-2) 0;
      border: none;
      background: none;
      color: var(--a2ui-accent);
      font-size: var(--a2ui-text-xs);
      font-family: var(--a2ui-font-family);
      font-weight: var(--a2ui-font-medium);
      cursor: pointer;
      border-radius: var(--a2ui-radius-md);
      width: 100%;
      transition: background 0.12s ease;
    }

    .sources-show-all:hover {
      background: var(--a2ui-bg-secondary);
    }

    /* ── Sources: auto collapse via container query ───── */

    @container (max-width: 900px) {
      .response-layout.pos-auto {
        flex-direction: column;
        margin-right: 40px;
        gap: var(--a2ui-space-4);
      }

      .response-layout.pos-auto .sources-panel {
        width: 100%;
        position: static;
        order: 1;
      }

      .response-layout.pos-auto .sources-list {
        overflow-x: auto;
        gap: var(--a2ui-space-1);
        padding-bottom: var(--a2ui-space-1);
        scrollbar-width: thin;
      }

      .response-layout.pos-auto .source-card {
        align-items: center;
        flex-shrink: 0;
        border-bottom: none;
        padding: var(--a2ui-space-2);
        background: var(--a2ui-bg-secondary);
        border-radius: var(--a2ui-radius-lg);
      }

      .response-layout.pos-auto .source-thumb,
      .response-layout.pos-auto .source-favicon-wrap,
      .response-layout.pos-auto .source-data-icon {
        width: 32px;
        height: 32px;
      }

      .response-layout.pos-auto .response-main {
        order: 2;
      }

      .response-layout.pos-auto .followups {
        order: 3;
      }
    }

    @container (max-width: 500px) {
      .response-layout.pos-auto .source-card,
      .response-layout.pos-bottom .source-card {
        width: 160px;
      }

      .response-layout.pos-auto .source-thumb,
      .response-layout.pos-auto .source-favicon-wrap,
      .response-layout.pos-auto .source-data-icon,
      .response-layout.pos-bottom .source-thumb,
      .response-layout.pos-bottom .source-favicon-wrap,
      .response-layout.pos-bottom .source-data-icon {
        height: 80px;
      }

      .source-desc {
        display: none;
      }
    }

    /* ── Action buttons (inline in .meta) ────────────── */

    .meta-actions {
      display: flex;
      align-items: center;
      gap: 2px;
      margin-left: auto;
      opacity: 0;
      transition: opacity 0.15s ease;
    }

    .message.assistant:hover .meta-actions,
    .meta-actions:focus-within {
      opacity: 1;
    }

    .action-btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 22px;
      height: 22px;
      padding: 0;
      border: none;
      border-radius: var(--a2ui-radius-sm);
      background: transparent;
      color: var(--a2ui-text-tertiary);
      cursor: pointer;
      transition:
        background 0.12s ease,
        color 0.12s ease;
    }

    .action-btn:hover {
      background: var(--a2ui-bg-tertiary);
      color: var(--a2ui-text-primary);
    }

    .action-btn.active {
      color: var(--a2ui-accent);
    }

    .action-btn svg {
      width: 13px;
      height: 13px;
    }

    .action-divider {
      width: 1px;
      height: 12px;
      background: var(--a2ui-border-subtle);
      margin: 0 1px;
    }

    .copied-toast {
      font-size: 10px;
      color: var(--a2ui-accent);
      padding: 0 2px;
      animation: fadeInOut 1.5s ease forwards;
    }

    @keyframes fadeInOut {
      0% {
        opacity: 0;
      }
      15% {
        opacity: 1;
      }
      75% {
        opacity: 1;
      }
      100% {
        opacity: 0;
      }
    }

    /* ── Follow-up suggestions ─────────────────────────── */

    .followups {
      display: flex;
      flex-direction: column;
      gap: var(--a2ui-space-2);
      width: 100%;
    }

    .followup {
      display: flex;
      align-items: center;
      gap: var(--a2ui-space-2);
      background: none;
      border: none;
      padding: var(--a2ui-space-1) 0;
      color: var(--a2ui-text-secondary);
      font-size: var(--a2ui-text-sm);
      font-family: var(--a2ui-font-family);
      cursor: pointer;
      text-align: left;
      transition: color 0.15s ease;
    }

    .followup:hover {
      color: var(--a2ui-text-primary);
    }

    .followup-icon {
      flex-shrink: 0;
      width: 16px;
      height: 16px;
      color: var(--a2ui-text-tertiary);
    }

    /* ── Responsive: Tablet (≤768px) ──────────────────── */

    @media (max-width: 768px) {
      :host {
        margin-bottom: var(--a2ui-space-4);
      }

      .message {
        gap: var(--a2ui-space-2);
      }

      .avatar {
        width: 28px;
        height: 28px;
        font-size: var(--a2ui-text-xs);
      }
    }

    /* ── Responsive: Mobile (≤480px) ─────────────────── */

    @media (max-width: 480px) {
      :host {
        margin-bottom: var(--a2ui-space-3);
      }

      .message {
        gap: var(--a2ui-space-2);
      }

      .avatar {
        width: 24px;
        height: 24px;
        font-size: 10px;
      }

      .user .bubble {
        padding: var(--a2ui-space-2) var(--a2ui-space-3);
        border-radius: var(--a2ui-radius-lg);
        border-bottom-right-radius: var(--a2ui-radius-sm);
      }

      .text-content {
        font-size: var(--a2ui-text-sm);
        line-height: var(--a2ui-leading-normal);
      }

      .meta {
        font-size: 10px;
      }

      .model-badge {
        font-size: 9px;
        padding: 1px 4px;
      }

      .followup {
        font-size: var(--a2ui-text-xs);
        gap: var(--a2ui-space-1);
      }

      .followup-icon {
        width: 14px;
        height: 14px;
      }

      .followups {
        gap: var(--a2ui-space-1);
        margin-top: var(--a2ui-space-2);
      }

      .image-strip a {
        width: 120px;
        height: 85px;
      }

      .meta-actions {
        opacity: 1;
      }
    }

    /* ── Markdown (assistant text) ─────────────── */
    ${unsafeCSS(markdownStyles)}
  `;

  @property({ type: Object }) message!: ChatMessage;
  @property({ type: Boolean }) editable = false;
  @property({ type: Boolean }) isLast = false;
  @state() private _editing = false;
  @state() private _editText = "";
  @state() private _copied = false;
  @state() private _liked: "up" | "down" | null = null;
  @state() private _sourcesExpanded = false;

  private _renderWandIcon() {
    return html`<svg class="wand-icon" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 2l1.09 3.41L16.5 6.5l-3.41 1.09L12 11l-1.09-3.41L7.5 6.5l3.41-1.09L12 2z"/>
      <path d="M18 12l.72 2.28L21 15l-2.28.72L18 18l-.72-2.28L15 15l2.28-.72L18 12z" opacity=".7"/>
      <path d="M5 16l.54 1.71L7.25 18.25l-1.71.54L5 20.5l-.54-1.71L2.75 18.25l1.71-.54L5 16z" opacity=".5"/>
    </svg>`;
  }

  private _renderProviderIcon(provider?: string) {
    const model = this.message.model?.toLowerCase() || '';
    const p = provider?.toLowerCase() || '';

    if (p.includes('anthropic') || model.includes('claude')) {
      return html`<svg class="provider-icon" viewBox="0 0 24 24" fill="currentColor">
        <path d="M13.827 3.52l3.603 11.117h-7.207L13.827 3.52zm-9.236 16.96L11.063 3.52h2.474l6.776 16.96h-2.586l-1.61-4.28H8.856l-1.679 4.28H4.591z"/>
      </svg>`;
    }
    if (p.includes('openai') || model.includes('gpt') || model.includes('o4')) {
      return html`<svg class="provider-icon" viewBox="0 0 24 24" fill="currentColor">
        <path d="M22.282 9.821a5.985 5.985 0 0 0-.516-4.91 6.046 6.046 0 0 0-6.51-2.9A6.065 6.065 0 0 0 4.981 4.18a5.998 5.998 0 0 0-3.998 2.9 6.042 6.042 0 0 0 .743 7.097 5.98 5.98 0 0 0 .51 4.911 6.051 6.051 0 0 0 6.515 2.9A5.985 5.985 0 0 0 13.26 24a6.056 6.056 0 0 0 5.772-4.206 5.99 5.99 0 0 0 3.997-2.9 6.056 6.056 0 0 0-.747-7.073zM13.26 22.43a4.476 4.476 0 0 1-2.876-1.04l.141-.081 4.779-2.758a.795.795 0 0 0 .392-.681v-6.737l2.02 1.168a.071.071 0 0 1 .038.052v5.583a4.504 4.504 0 0 1-4.494 4.494zM3.6 18.304a4.47 4.47 0 0 1-.535-3.014l.142.085 4.783 2.759a.771.771 0 0 0 .78 0l5.843-3.369v2.332a.08.08 0 0 1-.033.062L9.74 19.95a4.5 4.5 0 0 1-6.14-1.646zM2.34 7.896a4.485 4.485 0 0 1 2.366-1.973V11.6a.766.766 0 0 0 .388.676l5.815 3.355-2.02 1.168a.076.076 0 0 1-.071 0l-4.83-2.786A4.504 4.504 0 0 1 2.34 7.872zm16.597 3.855l-5.833-3.387L15.119 7.2a.076.076 0 0 1 .071 0l4.83 2.791a4.494 4.494 0 0 1-.676 8.105v-5.678a.79.79 0 0 0-.407-.667zm2.01-3.023l-.141-.085-4.774-2.782a.776.776 0 0 0-.785 0L9.409 9.23V6.897a.066.066 0 0 1 .028-.061l4.83-2.787a4.5 4.5 0 0 1 6.68 4.66zm-12.64 4.135l-2.02-1.164a.08.08 0 0 1-.038-.057V6.075a4.5 4.5 0 0 1 7.375-3.453l-.142.08L8.704 5.46a.795.795 0 0 0-.393.681zm1.097-2.365l2.602-1.5 2.607 1.5v2.999l-2.597 1.5-2.607-1.5z"/>
      </svg>`;
    }
    if (p.includes('google') || model.includes('gemini')) {
      return html`<svg class="provider-icon" viewBox="0 0 24 24" fill="currentColor">
        <path d="M12 24c6.627 0 12-5.373 12-12S18.627 0 12 0 0 5.373 0 12s5.373 12 12 12z" fill="url(#gemini_g)"/>
        <defs><linearGradient id="gemini_g" x1="0" y1="12" x2="24" y2="12" gradientUnits="userSpaceOnUse">
          <stop stop-color="#4285F4"/><stop offset="1" stop-color="#886FBF"/>
        </linearGradient></defs>
        <path d="M12 4.5c4.136 0 7.5 3.364 7.5 7.5s-3.364 7.5-7.5 7.5S4.5 16.136 4.5 12 7.864 4.5 12 4.5z" fill="white" fill-opacity=".25"/>
      </svg>`;
    }
    return html`<svg class="provider-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <circle cx="12" cy="12" r="3"/><path d="M12 1v4m0 14v4M4.22 4.22l2.83 2.83m9.9 9.9l2.83 2.83M1 12h4m14 0h4M4.22 19.78l2.83-2.83m9.9-9.9l2.83-2.83"/>
    </svg>`;
  }

  private _startEdit() {
    if (!this.editable || this.message.role !== "user") return;
    this._editText = this.message.content;
    this._editing = true;
    this.requestUpdate();
    setTimeout(() => {
      const ta =
        this.shadowRoot?.querySelector<HTMLTextAreaElement>(".edit-textarea");
      if (ta) {
        ta.focus();
        ta.setSelectionRange(ta.value.length, ta.value.length);
        this._autoResize(ta);
      }
    }, 0);
  }

  private _cancelEdit() {
    this._editing = false;
  }

  private _submitEdit() {
    const trimmed = this._editText.trim();
    if (!trimmed || trimmed === this.message.content) {
      this._editing = false;
      return;
    }
    this._editing = false;
    this.dispatchEvent(
      new CustomEvent("edit-message", {
        detail: { messageId: this.message.id, newContent: trimmed },
        bubbles: true,
        composed: true,
      }),
    );
  }

  private _handleEditKeydown(e: KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      this._submitEdit();
    } else if (e.key === "Escape") {
      this._cancelEdit();
    }
  }

  private _autoResize(el: HTMLTextAreaElement) {
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 200) + "px";
  }

  private async _copyResponse() {
    const text = this.message.content || "";
    try {
      await navigator.clipboard.writeText(text);
      this._copied = true;
      setTimeout(() => {
        this._copied = false;
      }, 1500);
    } catch {
      /* fallback */
    }
  }

  private _regenerate() {
    this.dispatchEvent(
      new CustomEvent("regenerate-message", {
        detail: { messageId: this.message.id },
        bubbles: true,
        composed: true,
      }),
    );
  }

  private _toggleLike(dir: "up" | "down") {
    this._liked = this._liked === dir ? null : dir;
  }

  private _deletePrompt() {
    this.dispatchEvent(
      new CustomEvent("delete-message", {
        detail: { messageId: this.message.id },
        bubbles: true,
        composed: true,
      }),
    );
  }

  private _getDomain(url: string): string {
    try {
      return new URL(url).hostname.replace(/^www\./, "");
    } catch {
      return url;
    }
  }

  private _getFavicon(url: string): string {
    try {
      const domain = new URL(url).hostname;
      return `https://www.google.com/s2/favicons?domain=${domain}&sz=32`;
    } catch {
      return "";
    }
  }

  private _renderSources(sources: SourceCitation[]) {
    if (!sources?.length) return nothing;

    const total = sources.length;
    const previewCount = 4;
    const visible = this._sourcesExpanded
      ? sources
      : sources.slice(0, previewCount);
    const hasMore = total > previewCount;

    return html`
      <div class="sources-panel">
        <div class="sources-header">
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <circle cx="12" cy="12" r="10" />
            <path d="M2 12h20" />
            <path
              d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"
            />
          </svg>
          <span class="sources-count"
            >${total} source${total !== 1 ? "s" : ""}</span
          >
        </div>
        <div class="sources-list">
          ${visible.map((s) =>
            s.type === "data"
              ? html`
                  <div class="source-card">
                    <div class="source-data-icon">
                      <svg
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="2"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                      >
                        <ellipse cx="12" cy="5" rx="9" ry="3" />
                        <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
                        <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
                      </svg>
                    </div>
                    <div class="source-info">
                      <div class="source-title">${s.title}</div>
                      <div class="source-meta">
                        <span class="source-domain">Data source</span>
                      </div>
                    </div>
                  </div>
                `
              : html`
                  <a
                    class="source-card"
                    href=${s.url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <div class="source-favicon-wrap">
                      <img
                        class="source-favicon"
                        src=${this._getFavicon(s.url)}
                        alt=""
                        loading="lazy"
                        @error=${(e: Event) => {
                          (e.target as HTMLImageElement).style.display = "none";
                        }}
                      />
                    </div>
                    <div class="source-info">
                      <div class="source-title">
                        ${s.title || this._getDomain(s.url)}
                      </div>
                      <div class="source-meta">
                        <img
                          class="source-meta-icon"
                          src=${this._getFavicon(s.url)}
                          alt=""
                          loading="lazy"
                        />
                        <span class="source-domain"
                          >${this._getDomain(s.url)}</span
                        >
                      </div>
                    </div>
                  </a>
                `,
          )}
        </div>
        ${hasMore && !this._sourcesExpanded
          ? html`
              <button
                class="sources-show-all"
                @click=${() => {
                  this._sourcesExpanded = true;
                }}
              >
                Show all
              </button>
            `
          : ""}
      </div>
    `;
  }

  private _renderActions() {
    return html`
      <span class="meta-actions">
        <button
          class="action-btn"
          title="Regenerate"
          @click=${this._regenerate}
        >
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <polyline points="23 4 23 10 17 10" />
            <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
          </svg>
        </button>
        <button class="action-btn" title="Copy" @click=${this._copyResponse}>
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
          </svg>
        </button>
        ${this.isLast
          ? html`
              <button
                class="action-btn"
                title="Delete"
                @click=${this._deletePrompt}
              >
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <polyline points="3 6 5 6 21 6" />
                  <path
                    d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"
                  />
                </svg>
              </button>
            `
          : ""}
        <div class="action-divider"></div>
        <button
          class="action-btn ${this._liked === "up" ? "active" : ""}"
          title="Good response"
          @click=${() => this._toggleLike("up")}
        >
          <svg
            viewBox="0 0 24 24"
            fill="${this._liked === "up" ? "currentColor" : "none"}"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <path
              d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"
            />
          </svg>
        </button>
        <button
          class="action-btn ${this._liked === "down" ? "active" : ""}"
          title="Needs improvement"
          @click=${() => this._toggleLike("down")}
        >
          <svg
            viewBox="0 0 24 24"
            fill="${this._liked === "down" ? "currentColor" : "none"}"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <path
              d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"
            />
          </svg>
        </button>
      </span>
    `;
  }

  private handleFollowup(text: string) {
    this.dispatchEvent(
      new CustomEvent("send-message", {
        detail: { message: text },
        bubbles: true,
        composed: true,
      }),
    );
  }

  connectedCallback() {
    super.connectedCallback();
    if (uiConfig.animateMessages) {
      this.setAttribute("animate", "");
    }
  }

  protected updated() {
    renderMermaidDiagrams(this.shadowRoot!);
  }

  private formatTime(timestamp: number): string {
    return new Date(timestamp).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  private _isSafeImageUrl(url: string): boolean {
    try {
      const parsed = new URL(url);
      return parsed.protocol === "https:" || parsed.protocol === "http:";
    } catch {
      return false;
    }
  }

  render() {
    const { role, content, a2ui, timestamp, model } = this.message;
    const isUser = role === "user";
    const hasSources = !isUser && this.message.sources?.length;

    return html`
      <div
        class="message ${role}"
        role="article"
        aria-label="${isUser ? "User" : "Assistant"} message"
      >
        <div class="avatar ${role}" aria-hidden="true">
          ${isUser
            ? this.message.avatarUrl
              ? html`<img src=${this.message.avatarUrl} alt="" />`
              : this.message.avatarInitials || "U"
            : "AI"}
        </div>
        <div class="content">
          ${isUser
            ? html`
                ${this._editing
                  ? html`
                      <div class="edit-container">
                        <textarea
                          class="edit-textarea"
                          .value=${this._editText}
                          @input=${(e: InputEvent) => {
                            const ta = e.target as HTMLTextAreaElement;
                            this._editText = ta.value;
                            this._autoResize(ta);
                          }}
                          @keydown=${this._handleEditKeydown}
                        ></textarea>
                        <div class="edit-actions">
                          <button
                            class="edit-btn cancel"
                            @click=${this._cancelEdit}
                          >
                            Cancel
                          </button>
                          <button
                            class="edit-btn submit"
                            ?disabled=${!this._editText.trim() ||
                            this._editText.trim() === content}
                            @click=${this._submitEdit}
                          >
                            Send
                          </button>
                        </div>
                      </div>
                    `
                  : html`
                      <div
                        class="bubble ${this.editable ? "editable" : ""}"
                        @dblclick=${this.editable
                          ? () => this._startEdit()
                          : nothing}
                        title=${this.editable ? "Double-click to edit" : ""}
                      >
                        <div class="text-content">${content}</div>
                      </div>
                    `}
              `
            : html`
                <div class="response-layout pos-${uiConfig.sourcesPosition}">
                  <div class="response-main">
                    <div class="bubble">
                      ${content
                        ? html` <div class="text-content">${md(content)}</div> `
                        : ""}
                      ${a2ui
                        ? html`
                            <div class="a2ui-content">
                              ${A2UIRenderer.render(a2ui)}
                            </div>
                          `
                        : ""}
                    </div>
                    ${this.message.images?.length
                      ? html`
                          <div class="image-strip">
                            ${this.message.images
                              .filter((url) => this._isSafeImageUrl(url))
                              .map(
                                (url) => html`
                                  <a
                                    href=${url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                  >
                                    <img
                                      src=${url}
                                      alt=""
                                      loading="lazy"
                                      @error=${(e: Event) => {
                                        (
                                          e.target as HTMLElement
                                        ).parentElement!.style.display = "none";
                                      }}
                                    />
                                  </a>
                                `,
                              )}
                          </div>
                        `
                      : ""}
                    <div class="meta">
                      ${model
                        ? html`<span class="model-badge">${this.message.modelUpgraded ? this._renderWandIcon() : ''}${this._renderProviderIcon(this.message.provider)} ${model}</span>`
                        : ""}
                      ${this.message.duration
                        ? html`
                            <span class="duration"
                              >${this.message.duration}s</span
                            >
                          `
                        : ""}
                      <span>${this.formatTime(timestamp)}</span>
                      ${this.message.style
                        ? html`
                            <span class="style-badge"
                              >${this.message.style.charAt(0).toUpperCase() +
                              this.message.style.slice(1)}</span
                            >
                          `
                        : ""}
                      ${uiConfig.showActions ? this._renderActions() : ""}
                    </div>
                  </div>
                  ${uiConfig.showSources && hasSources
                    ? this._renderSources(this.message.sources!)
                    : ""}
                  ${uiConfig.maxSuggestions > 0 &&
                  this.message.suggestions?.length
                    ? html`
                        <div class="followups">
                          ${this.message.suggestions
                            .slice(0, uiConfig.maxSuggestions)
                            .map(
                              (s) => html`
                                <button
                                  class="followup"
                                  aria-label="Follow up: ${s}"
                                  @click=${() => this.handleFollowup(s)}
                                >
                                  <svg
                                    class="followup-icon"
                                    viewBox="0 0 24 24"
                                    fill="none"
                                    stroke="currentColor"
                                    stroke-width="2"
                                    stroke-linecap="round"
                                    stroke-linejoin="round"
                                    aria-hidden="true"
                                  >
                                    <path d="M5 12h14M12 5l7 7-7 7" />
                                  </svg>
                                  ${s}
                                </button>
                              `,
                            )}
                        </div>
                      `
                    : ""}
                </div>
              `}
          ${isUser
            ? html`
                <div class="meta">
                  <span>${this.formatTime(timestamp)}</span>
                </div>
              `
            : ""}
        </div>
      </div>
    `;
  }
}
