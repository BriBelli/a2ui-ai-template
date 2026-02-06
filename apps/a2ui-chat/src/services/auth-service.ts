/**
 * Auth0 Authentication Service
 *
 * Wraps @auth0/auth0-spa-js for redirect flows (Google, signup)
 * and uses direct Auth0 API for email/password login (Resource Owner Password Grant).
 *
 * Auth0 credentials ported from BriBelli/Demo-App.
 * Override via VITE_AUTH0_DOMAIN and VITE_AUTH0_CLIENT_ID env vars.
 */

import { Auth0Client } from '@auth0/auth0-spa-js';

// ── Auth0 Configuration ───────────────────────────────────────

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const env = (import.meta as any).env ?? {};
const AUTH0_DOMAIN = env.VITE_AUTH0_DOMAIN || 'dev-iep8px1emd3ipkkp.us.auth0.com';
const AUTH0_CLIENT_ID = env.VITE_AUTH0_CLIENT_ID || '3Z6o8Yvey48FOeGHILCr9czwJ6iHuQpQ';

const STORAGE_KEYS = {
  TOKENS: 'a2ui_auth_tokens',
  USER: 'a2ui_auth_user',
} as const;

// ── Types ─────────────────────────────────────────────────────

export interface AuthUser {
  email: string;
  name: string;
  picture?: string;
  sub: string;
  email_verified?: boolean;
  nickname?: string;
  [key: string]: unknown;
}

// ── Service ───────────────────────────────────────────────────

class AuthService extends EventTarget {
  private client!: Auth0Client;
  private _isAuthenticated = false;
  private _isLoading = true;
  private _user: AuthUser | null = null;

  get isAuthenticated() { return this._isAuthenticated; }
  get isLoading() { return this._isLoading; }
  get user() { return this._user; }

  /** Notify listeners that auth state changed */
  private notify() {
    this.dispatchEvent(new Event('change'));
  }

  /** Initialize auth — call once on app load */
  async init(): Promise<void> {
    this.client = new Auth0Client({
      domain: AUTH0_DOMAIN,
      clientId: AUTH0_CLIENT_ID,
      authorizationParams: {
        redirect_uri: window.location.origin,
      },
      cacheLocation: 'localstorage',
    });

    try {
      // Handle OAuth redirect callback
      const params = new URLSearchParams(window.location.search);
      if (params.has('code') && params.has('state')) {
        await this.client.handleRedirectCallback();
        window.history.replaceState({}, document.title, window.location.pathname);
      }

      // Check Auth0 SDK session (covers redirect-based login + Google)
      if (await this.client.isAuthenticated()) {
        this._user = (await this.client.getUser()) as AuthUser;
        this._isAuthenticated = true;
      } else {
        // Check custom login session (email/password via direct API)
        this.restoreCustomSession();
      }
    } catch (err) {
      console.error('Auth init error:', err);
      this.restoreCustomSession();
    }

    this._isLoading = false;
    this.notify();
  }

  // ── Custom session (email/password login) ─────────────────

  private restoreCustomSession() {
    try {
      const tokensRaw = localStorage.getItem(STORAGE_KEYS.TOKENS);
      const userRaw = localStorage.getItem(STORAGE_KEYS.USER);

      if (tokensRaw && userRaw) {
        const tokens = JSON.parse(tokensRaw);
        if (tokens.expires_at && Date.now() < tokens.expires_at) {
          this._user = JSON.parse(userRaw);
          this._isAuthenticated = true;
          return;
        }
      }
    } catch { /* invalid data */ }

    this.clearCustomSession();
  }

  private clearCustomSession() {
    localStorage.removeItem(STORAGE_KEYS.TOKENS);
    localStorage.removeItem(STORAGE_KEYS.USER);
  }

  // ── Login methods ─────────────────────────────────────────

  /**
   * Email/password login via Auth0 Resource Owner Password Grant.
   * Tries multiple connection names (matching Demo-App behavior).
   */
  async loginWithCredentials(email: string, password: string): Promise<void> {
    const connections = ['Username-Password-Authentication', 'email', 'database', null];
    let lastError = 'Authentication failed';

    for (const connection of connections) {
      const body: Record<string, string> = {
        grant_type: 'password',
        username: email,
        password,
        client_id: AUTH0_CLIENT_ID,
        scope: 'openid profile email',
      };
      if (connection) body.connection = connection;

      const response = await fetch(`https://${AUTH0_DOMAIN}/oauth/token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (response.ok) {
        const data = await response.json();

        // Fetch user profile
        const userResp = await fetch(`https://${AUTH0_DOMAIN}/userinfo`, {
          headers: { Authorization: `Bearer ${data.access_token}` },
        });
        if (!userResp.ok) throw new Error('Failed to fetch user profile');

        const user = await userResp.json();

        // Persist session
        localStorage.setItem(STORAGE_KEYS.TOKENS, JSON.stringify({
          ...data,
          expires_at: Date.now() + (data.expires_in * 1000),
        }));
        localStorage.setItem(STORAGE_KEYS.USER, JSON.stringify(user));

        this._user = user;
        this._isAuthenticated = true;
        this.notify();
        return;
      }

      const errData = await response.json().catch(() => ({}));
      lastError = errData.error_description || errData.error || lastError;
    }

    throw new Error(lastError);
  }

  /** Redirect to Auth0 hosted login (Google social, etc.) */
  async loginWithRedirect(): Promise<void> {
    await this.client.loginWithRedirect();
  }

  /** Redirect to Auth0 signup page */
  async signupWithRedirect(): Promise<void> {
    await this.client.loginWithRedirect({
      authorizationParams: { screen_hint: 'signup' },
    });
  }

  /** Google social login via Auth0 redirect */
  async loginWithGoogle(): Promise<void> {
    await this.client.loginWithRedirect({
      authorizationParams: { connection: 'google-oauth2' },
    });
  }

  /** Send password reset email */
  async resetPassword(email: string): Promise<void> {
    const response = await fetch(`https://${AUTH0_DOMAIN}/dbconnections/change_password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        client_id: AUTH0_CLIENT_ID,
        email,
        connection: 'Username-Password-Authentication',
      }),
    });
    if (!response.ok) throw new Error('Failed to send password reset email');
  }

  /** Log out and clear all sessions */
  async logout(): Promise<void> {
    this.clearCustomSession();
    this._isAuthenticated = false;
    this._user = null;
    this.notify();

    try {
      if (await this.client.isAuthenticated()) {
        await this.client.logout({
          logoutParams: { returnTo: window.location.origin },
        });
        return;
      }
    } catch { /* SDK not authenticated */ }

    window.location.reload();
  }
}

/** Singleton auth service instance */
export const authService = new AuthService();
