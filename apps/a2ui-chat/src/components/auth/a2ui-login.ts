/**
 * A2UI Login Modal
 *
 * Dark-themed login/signup/forgot-password modal.
 * Ported from BriBelli/Demo-App CustomLogin.tsx, restyled for a2ui dark theme.
 */

import { LitElement, html, css } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { authService } from '../../services/auth-service';

type ViewMode = 'login' | 'signup' | 'forgot';

@customElement('a2ui-login')
export class A2UILogin extends LitElement {
  static styles = css`
    /* ── Overlay ────────────────────────────────────────── */
    :host {
      display: flex;
      align-items: center;
      justify-content: center;
      position: fixed;
      inset: 0;
      z-index: var(--a2ui-z-modal);
      background: rgba(0, 0, 0, 0.6);
      backdrop-filter: blur(6px);
      animation: overlayIn 0.2s ease;
    }

    @keyframes overlayIn {
      from { opacity: 0; }
      to { opacity: 1; }
    }

    /* ── Modal ──────────────────────────────────────────── */
    .modal {
      background: var(--a2ui-bg-primary);
      border: 1px solid var(--a2ui-border-default);
      border-radius: var(--a2ui-radius-xl);
      padding: var(--a2ui-space-8);
      width: 100%;
      max-width: 380px;
      position: relative;
      animation: modalIn 0.25s cubic-bezier(0.22, 1, 0.36, 1);
    }

    @keyframes modalIn {
      from { opacity: 0; transform: translateY(-12px) scale(0.97); }
      to   { opacity: 1; transform: translateY(0) scale(1); }
    }

    .close-btn {
      position: absolute;
      top: var(--a2ui-space-4);
      right: var(--a2ui-space-4);
      background: none;
      border: none;
      color: var(--a2ui-text-tertiary);
      font-size: 20px;
      cursor: pointer;
      width: 28px;
      height: 28px;
      border-radius: var(--a2ui-radius-full);
      display: flex;
      align-items: center;
      justify-content: center;
      transition: background-color 0.15s ease, color 0.15s ease;
    }

    .close-btn:hover {
      background: var(--a2ui-bg-hover);
      color: var(--a2ui-text-primary);
    }

    /* ── Header ─────────────────────────────────────────── */
    .header {
      text-align: center;
      margin-bottom: var(--a2ui-space-6);
    }

    .header h2 {
      margin: 0 0 var(--a2ui-space-1) 0;
      font-size: var(--a2ui-text-xl);
      font-weight: var(--a2ui-font-medium);
      color: var(--a2ui-text-primary);
    }

    .header p {
      margin: 0;
      font-size: var(--a2ui-text-sm);
      color: var(--a2ui-text-secondary);
    }

    /* ── Form ───────────────────────────────────────────── */
    .form-group {
      margin-bottom: var(--a2ui-space-4);
    }

    label {
      display: block;
      margin-bottom: var(--a2ui-space-1);
      font-size: var(--a2ui-text-sm);
      font-weight: var(--a2ui-font-medium);
      color: var(--a2ui-text-secondary);
    }

    input {
      width: 100%;
      padding: var(--a2ui-space-3);
      background: var(--a2ui-bg-input);
      border: 1px solid var(--a2ui-border-default);
      border-radius: var(--a2ui-radius-md);
      color: var(--a2ui-text-primary);
      font-size: var(--a2ui-text-md);
      font-family: var(--a2ui-font-family);
      box-sizing: border-box;
      transition: border-color 0.15s ease;
    }

    input:focus {
      outline: none;
      border-color: var(--a2ui-accent);
    }

    input::placeholder {
      color: var(--a2ui-text-disabled);
    }

    input:disabled {
      opacity: 0.5;
    }

    /* ── Buttons ─────────────────────────────────────────── */
    .submit-btn {
      width: 100%;
      padding: var(--a2ui-space-3);
      background: var(--a2ui-accent);
      color: var(--a2ui-text-inverse);
      border: none;
      border-radius: var(--a2ui-radius-md);
      font-size: var(--a2ui-text-md);
      font-weight: var(--a2ui-font-medium);
      font-family: var(--a2ui-font-family);
      cursor: pointer;
      transition: background-color 0.15s ease;
      margin-top: var(--a2ui-space-2);
    }

    .submit-btn:hover:not(:disabled) {
      background: var(--a2ui-accent-hover);
    }

    .submit-btn:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }

    /* ── Forgot password link ────────────────────────────── */
    .forgot-link {
      text-align: right;
      margin-bottom: var(--a2ui-space-3);
    }

    .link-btn {
      background: none;
      border: none;
      color: var(--a2ui-accent);
      font-size: var(--a2ui-text-sm);
      font-family: var(--a2ui-font-family);
      cursor: pointer;
      padding: 0;
      transition: color 0.15s ease;
    }

    .link-btn:hover {
      color: var(--a2ui-accent-hover);
      text-decoration: underline;
    }

    .link-btn:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }

    /* ── Footer (toggle login/signup) ────────────────────── */
    .footer {
      text-align: center;
      margin-top: var(--a2ui-space-4);
      font-size: var(--a2ui-text-sm);
      color: var(--a2ui-text-secondary);
    }

    /* ── Divider ─────────────────────────────────────────── */
    .divider {
      display: flex;
      align-items: center;
      gap: var(--a2ui-space-3);
      margin: var(--a2ui-space-5) 0;
      color: var(--a2ui-text-tertiary);
      font-size: var(--a2ui-text-sm);
    }

    .divider::before,
    .divider::after {
      content: '';
      flex: 1;
      height: 1px;
      background: var(--a2ui-border-default);
    }

    /* ── Google button ───────────────────────────────────── */
    .google-btn {
      width: 100%;
      padding: var(--a2ui-space-3);
      background: var(--a2ui-bg-secondary);
      border: 1px solid var(--a2ui-border-default);
      border-radius: var(--a2ui-radius-md);
      color: var(--a2ui-text-primary);
      font-size: var(--a2ui-text-md);
      font-family: var(--a2ui-font-family);
      cursor: pointer;
      transition: background-color 0.15s ease, border-color 0.15s ease;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: var(--a2ui-space-2);
    }

    .google-btn:hover {
      background: var(--a2ui-bg-tertiary);
      border-color: var(--a2ui-border-strong);
    }

    .google-icon {
      width: 18px;
      height: 18px;
    }

    /* ── Error ───────────────────────────────────────────── */
    .error {
      background: var(--a2ui-error-bg);
      border: 1px solid rgba(242, 139, 130, 0.3);
      border-radius: var(--a2ui-radius-md);
      padding: var(--a2ui-space-3);
      margin-bottom: var(--a2ui-space-4);
      font-size: var(--a2ui-text-sm);
      color: var(--a2ui-error);
    }

    /* ── Reset success ───────────────────────────────────── */
    .reset-success {
      text-align: center;
    }

    .reset-success .icon {
      font-size: 40px;
      margin-bottom: var(--a2ui-space-3);
    }

    .reset-success h2 {
      color: var(--a2ui-success);
    }

    .reset-success p {
      color: var(--a2ui-text-secondary);
      font-size: var(--a2ui-text-sm);
      line-height: var(--a2ui-leading-relaxed);
      margin: var(--a2ui-space-2) 0;
    }
  `;

  @state() private view: ViewMode = 'login';
  @state() private email = '';
  @state() private password = '';
  @state() private error: string | null = null;
  @state() private isLoading = false;
  @state() private resetSent = false;

  private handleClose() {
    this.dispatchEvent(new Event('close', { bubbles: true, composed: true }));
  }

  private handleOverlayClick(e: MouseEvent) {
    if (e.target === e.currentTarget) this.handleClose();
  }

  private async handleSubmit(e: Event) {
    e.preventDefault();
    this.isLoading = true;
    this.error = null;

    try {
      if (this.view === 'login') {
        await authService.loginWithCredentials(this.email, this.password);
      } else if (this.view === 'signup') {
        await authService.signupWithRedirect();
      } else if (this.view === 'forgot') {
        await authService.resetPassword(this.email);
        this.resetSent = true;
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Something went wrong';
      if (msg.includes('Wrong email or password') || msg.includes('invalid_grant')) {
        this.error = 'Invalid email or password. Please try again.';
      } else if (msg.includes('not configured')) {
        this.error = 'Authentication service error. Please try again later.';
      } else {
        this.error = msg;
      }
    } finally {
      this.isLoading = false;
    }
  }

  private async handleGoogle() {
    await authService.loginWithGoogle();
  }

  private switchView(view: ViewMode) {
    this.view = view;
    this.error = null;
    this.resetSent = false;
  }

  // ── Render helpers ──────────────────────────────────────

  private renderResetSuccess() {
    return html`
      <div class="reset-success">
        <div class="icon">&#x2709;&#xFE0F;</div>
        <h2>Check your email</h2>
        <p>We've sent a password reset link to <strong>${this.email}</strong></p>
        <p style="font-size:11px; color:var(--a2ui-text-tertiary);">
          Didn't receive it? Check your spam folder or try again.
        </p>
        <button class="submit-btn" style="margin-top:var(--a2ui-space-4)"
          @click=${() => this.switchView('login')}>
          Back to Sign In
        </button>
      </div>
    `;
  }

  private renderForm() {
    const titles: Record<ViewMode, { h: string; p: string }> = {
      login:  { h: 'Welcome back',        p: 'Sign in to A2UI Chat' },
      signup: { h: 'Create your account', p: 'Get started with A2UI Chat' },
      forgot: { h: 'Reset your password', p: 'Enter your email to receive a reset link' },
    };

    const { h, p } = titles[this.view];
    const btnLabel = this.view === 'login' ? 'Sign In'
      : this.view === 'signup' ? 'Create Account'
      : 'Send Reset Link';

    return html`
      <div class="header">
        <h2>${h}</h2>
        <p>${p}</p>
      </div>

      ${this.error ? html`<div class="error">${this.error}</div>` : ''}

      <form @submit=${this.handleSubmit}>
        <div class="form-group">
          <label>Email</label>
          <input
            type="email"
            placeholder="you@example.com"
            .value=${this.email}
            @input=${(e: InputEvent) => this.email = (e.target as HTMLInputElement).value}
            required
            ?disabled=${this.isLoading}
          />
        </div>

        ${this.view !== 'forgot' ? html`
          <div class="form-group">
            <label>Password</label>
            <input
              type="password"
              placeholder="Enter your password"
              .value=${this.password}
              @input=${(e: InputEvent) => this.password = (e.target as HTMLInputElement).value}
              required
              ?disabled=${this.isLoading}
            />
          </div>
        ` : ''}

        ${this.view === 'login' ? html`
          <div class="forgot-link">
            <button type="button" class="link-btn"
              ?disabled=${this.isLoading}
              @click=${() => this.switchView('forgot')}>
              Forgot your password?
            </button>
          </div>
        ` : ''}

        <button class="submit-btn" type="submit" ?disabled=${this.isLoading}>
          ${this.isLoading ? 'Please wait...' : btnLabel}
        </button>
      </form>

      <!-- Toggle login / signup -->
      <div class="footer">
        ${this.view === 'login' ? html`
          Don't have an account?
          <button class="link-btn" @click=${() => this.switchView('signup')}
            ?disabled=${this.isLoading}>Sign up</button>
        ` : this.view === 'signup' ? html`
          Already have an account?
          <button class="link-btn" @click=${() => this.switchView('login')}
            ?disabled=${this.isLoading}>Sign in</button>
        ` : html`
          Remember your password?
          <button class="link-btn" @click=${() => this.switchView('login')}
            ?disabled=${this.isLoading}>Back to Sign In</button>
        `}
      </div>

      <!-- Social login (not for forgot view) -->
      ${this.view !== 'forgot' ? html`
        <div class="divider"><span>or</span></div>
        <button class="google-btn" @click=${this.handleGoogle} ?disabled=${this.isLoading}>
          <svg class="google-icon" viewBox="0 0 24 24">
            <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"/>
            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
            <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
          </svg>
          Continue with Google
        </button>
      ` : ''}
    `;
  }

  render() {
    return html`
      <div @click=${this.handleOverlayClick}>
        <div class="modal" @click=${(e: Event) => e.stopPropagation()}>
          <button class="close-btn" @click=${this.handleClose}>&times;</button>
          ${this.view === 'forgot' && this.resetSent
            ? this.renderResetSuccess()
            : this.renderForm()}
        </div>
      </div>
    `;
  }
}
