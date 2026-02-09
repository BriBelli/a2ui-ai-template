# A2UI Component Architecture

A2UI follows **Atomic Design** principles to create a structured, composable, and scalable UI component system. Components are organized into three tiers that build on each other.

---

## Tier 1 — Atoms

The smallest, indivisible building blocks. Each renders a single visual element.

| Component      | Description                          | Key Props                                          |
|----------------|--------------------------------------|-----------------------------------------------------|
| `text`         | Typography (headings, body, code)    | `content`, `variant` (h1-h3, body, caption, label, code) |
| `chip`         | Badge / tag / status label           | `label`, `variant` (default, primary, success, warning, error) |
| `button`       | Clickable action                     | `label`, `variant`, `size`, `disabled`              |
| `link`         | Anchor / navigation                  | `href`, `text`, `external`                          |
| `image`        | Media display with fallback          | `src`, `alt`, `caption`                             |
| `separator`    | Horizontal/vertical divider          | `orientation`, `label` (optional centered text)     |
| `progress`     | Progress / gauge bar                 | `label`, `value`, `max`, `variant`, `showValue`     |

**Principle**: An atom has no children and represents one visual concept.

---

## Tier 2 — Molecules

Composed of atoms. Each molecule serves **one clear purpose** (data display, interaction, organization).

| Component      | Description                          | Composed Of                           |
|----------------|--------------------------------------|---------------------------------------|
| `stat`         | KPI / metric display                 | text (label, value) + badge (trend)   |
| `list`         | Ordered / unordered / checklist      | text items + icons                    |
| `data-table`   | Tabular data with columns            | text + layout                         |
| `chart`        | Visualization (bar, line, pie, etc.) | Chart.js canvas + labels              |
| `accordion`    | Expandable FAQ / detail sections     | text (title, content) + icon (chevron)|
| `tabs`         | Tabbed content panels                | text (labels) + content panels        |
| `alert`        | Status banner (info, warning, error) | icon + text (title, description)      |

**Principle**: A molecule combines atoms to perform a single, well-defined function.

---

## Tier 3 — Organisms (Layout)

Structural containers that compose atoms and molecules into layouts.

| Component      | Description                          | Layout Model     |
|----------------|--------------------------------------|-------------------|
| `card`         | Titled container with content        | Flex column       |
| `container`    | Flexbox wrapper (vertical/horizontal)| Flexbox           |
| `grid`         | CSS Grid (1–6 columns, responsive)   | CSS Grid          |

**Principle**: Organisms define spatial relationships. They hold molecules and atoms but have minimal visual styling of their own.

---

## Domain Patterns (Composition Recipes)

These are not components — they're **recipes** that the AI uses to compose components for specific domains.

| Pattern      | Structure                                                           |
|-------------|----------------------------------------------------------------------|
| **Dashboard** | `grid` of `stat` → `chart` → `data-table`                         |
| **Stock**     | `stat` → `chart(line, fillArea)` → `data-table` → `alert`         |
| **Weather**   | `stat(temp + condition)` → optional `grid` of day stats            |
| **Compare**   | `grid` of `card` with `list` → `data-table` → `chart(bar)`       |
| **How-To**    | `card` → `list(numbered)`                                         |
| **FAQ**       | `accordion`                                                        |
| **Gallery**   | `grid(columns:3)` → `image` per URL                               |
| **Content**   | `card` → `text` + `list` + `separator` + `chip` tags              |
| **Status**    | `card` → `progress` bars per metric                                |

---

## File Structure

```
apps/a2ui-chat/src/components/a2ui/
├── a2ui-text.ts          # Atom
├── a2ui-chip.ts          # Atom
├── a2ui-button.ts        # Atom
├── a2ui-link.ts          # Atom
├── a2ui-image.ts         # Atom
├── a2ui-separator.ts     # Atom
├── a2ui-progress.ts      # Atom
├── a2ui-stat.ts          # Molecule
├── a2ui-list.ts          # Molecule
├── a2ui-data-table.ts    # Molecule
├── a2ui-chart.ts         # Molecule
├── a2ui-accordion.ts     # Molecule
├── a2ui-tabs.ts          # Molecule
├── a2ui-alert.ts         # Molecule
├── a2ui-card.ts          # Organism
├── a2ui-container.ts     # Organism
└── a2ui-grid.ts          # Organism
```

## Adding New Components

1. **Determine the tier**: Atom (single element), Molecule (composed atoms), Organism (layout).
2. **Create the Lit component** in `apps/a2ui-chat/src/components/a2ui/`.
3. **Register the import** in `apps/a2ui-chat/src/main.ts` under the correct tier comment.
4. **Add renderer mapping** in `apps/a2ui-chat/src/services/a2ui-renderer.ts`.
5. **Add TypeScript types** in `libs/a2ui-core/src/types.ts`.
6. **Update LLM schema** in `backend/llm_providers.py` — add to the correct tier in `A2UI_SCHEMA` and create/update relevant patterns.
