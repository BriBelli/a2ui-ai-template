/**
 * A2UI Pattern Registry
 *
 * Reusable composition patterns (recipes) that define how
 * A2UI primitives combine for common response types.
 *
 * Patterns use {{placeholder}} syntax for dynamic data.
 * They serve two purposes:
 *   1. Human reference — contributors can see and add patterns.
 *   2. Prompt generation — auto-generate LLM system prompt sections.
 */

import stockDetail from './stock-detail.json';
import comparison from './comparison.json';
import dashboard from './dashboard.json';
import weather from './weather.json';
import content from './content.json';
import howTo from './how-to.json';

export interface A2UIPattern {
  /** Unique name (kebab-case) */
  name: string;
  /** Human-readable description */
  description: string;
  /** Keywords that suggest this pattern is relevant */
  match: string[];
  /** A2UI JSON template with {{placeholder}} values */
  template: Record<string, unknown>;
}

/** All registered patterns */
export const patterns: A2UIPattern[] = [
  stockDetail as A2UIPattern,
  comparison as A2UIPattern,
  dashboard as A2UIPattern,
  weather as A2UIPattern,
  content as A2UIPattern,
  howTo as A2UIPattern,
];

/**
 * Find patterns whose match keywords overlap with the query.
 * Returns patterns sorted by number of keyword hits (best first).
 */
export function matchPatterns(query: string): A2UIPattern[] {
  const lower = query.toLowerCase();
  return patterns
    .map(p => ({
      pattern: p,
      hits: p.match.filter(kw => lower.includes(kw)).length,
    }))
    .filter(m => m.hits > 0)
    .sort((a, b) => b.hits - a.hits)
    .map(m => m.pattern);
}

/**
 * Get a pattern by name.
 */
export function getPattern(name: string): A2UIPattern | undefined {
  return patterns.find(p => p.name === name);
}
