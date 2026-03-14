/**
 * Data Source Registry
 *
 * Manages the set of external data sources available to the AI pipeline.
 * Sources are fetched from the backend and can be toggled (pinned) by users.
 */

export type SourceStatus =
  | 'inactive'
  | 'ai-active'
  | 'user-pinned'
  | 'ai-active+pinned'
  | 'unavailable';

export interface DataSourceInfo {
  id: string;
  name: string;
  description: string;
  available: boolean;
  endpointCount: number;
}

class DataSourceRegistry extends EventTarget {
  private _sources: DataSourceInfo[] = [];
  private _pinned = new Set<string>();
  private _aiActive = new Set<string>();
  private _fetched = false;

  get fetched(): boolean {
    return this._fetched;
  }

  get allSources(): DataSourceInfo[] {
    return this._sources;
  }

  async fetchSources(): Promise<void> {
    try {
      const resp = await fetch('/api/data-sources');
      if (resp.ok) {
        const data = await resp.json();
        this._sources = data.sources ?? [];
      }
    } catch {
      this._sources = [];
    }
    this._fetched = true;
    this.dispatchEvent(new Event('change'));
  }

  getStatus(id: string): SourceStatus {
    const src = this._sources.find((s) => s.id === id);
    if (!src || !src.available) return 'unavailable';
    const pinned = this._pinned.has(id);
    const aiActive = this._aiActive.has(id);
    if (aiActive && pinned) return 'ai-active+pinned';
    if (aiActive) return 'ai-active';
    if (pinned) return 'user-pinned';
    return 'inactive';
  }

  toggleSource(id: string): void {
    if (this._pinned.has(id)) {
      this._pinned.delete(id);
    } else {
      this._pinned.add(id);
    }
    this.dispatchEvent(new Event('change'));
  }

  setAiActive(ids: string[]): void {
    this._aiActive = new Set(ids);
    this.dispatchEvent(new Event('change'));
  }

  get pinnedIds(): string[] {
    return [...this._pinned];
  }
}

export const dataSourceRegistry = new DataSourceRegistry();
