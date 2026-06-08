## Context

OfflineU is a Flask server-rendered app with three Jinja2 templates, each containing its own inline `<style>` block. The current CSS is functional but inconsistent: hex colors are scattered, spacing lacks a system, and there are no design tokens. The dark theme uses harsh grays (`#1a1a1a`, `#2d2d2d`, `#3d3d3d`, `#444`) with a single accent (`#007acc`). Typography relies on the system font stack. Transitions are minimal (a single `0.3s` hover on buttons and the progress bar).

The goal is a CSS-only refresh — no new dependencies, no framework, no Python changes.

## Goals / Non-Goals

**Goals:**
- Establish a CSS custom property system (design tokens) for colors, spacing, typography, radii, shadows, and transitions
- Introduce Inter (Google Fonts) as the primary typeface with a system font fallback
- Refine the dark palette: softer, deeper backgrounds with proper elevation levels
- Standardize component styles: buttons, cards, inputs, modals, progress bar, tree items, lesson items
- Add subtle, purposeful animations: tree expand/collapse, card elevation on hover, modal backdrop blur, progress bar shimmer
- Polish the empty state and lesson viewer with the same token system
- Keep all CSS inline in each template (no separate stylesheet, no build step)

**Non-Goals:**
- Changing HTML structure or adding new elements (except where animation requires a wrapper)
- Adding a CSS framework (Bootstrap, Tailwind, etc.)
- JS-driven animations (pure CSS transitions and keyframes only)
- Mobile/responsive redesign (existing media queries preserved)
- Dark/light theme switcher (stays dark-only)

## Decisions

### Design tokens via CSS custom properties
Define all visual values as `:root` custom properties. This means one edit propagates everywhere, and future theme work (light mode) becomes a single `[data-theme="light"]` block.

Token categories:
- `--color-bg-*` (body, surface, elevated)
- `--color-text-*` (primary, secondary, muted)
- `--color-accent-*` (primary blue, success green, and the existing type colors)
- `--font-*` (family, size scale, weight)
- `--space-*` (4px-based scale: 4, 8, 12, 16, 20, 24, 32)
- `--radius-*` (sm, md, lg, full)
- `--shadow-*` (sm, md, lg)
- `--transition-*` (fast 150ms, base 250ms, slow 400ms)

**Alternative considered**: SASS/SCSS variables. Rejected — requires a build step. CSS custom properties are native, runtime-dynamic, and sufficient here.

### Font: Inter
Google Fonts, weight 400+500+600+700 via `<link>` in `<head>`. It's modern, legible at small sizes, and has an extensive weight range. Fallback: `system-ui, -apple-system, sans-serif`.

**Alternative considered**: No web font (status quo). Rejected — a good typeface is the single highest-impact visual change. Inter adds ~50KB (woff2 subset).

### Color palette: deep slate dark
Move away from flat grays toward a deep blue-gray (slate) dark scheme:
- Body: `#0f1117` (near-black blue-gray)
- Surface (cards): `#1a1d27`
- Elevated (modals, hover): `#22262f`
- Text primary: `#e4e6ed` (off-white)
- Text secondary: `#8b8fa3`
- Accent primary: `#3b82f6` (modern blue)
- Accent success: `#22c55e`
- Use opacity/alpha where possible (`rgba(255,255,255,0.05)` for borders)

**Alternative considered**: True black (`#000`). Rejected — too harsh, causes eye strain. Deep blue-gray is easier on the eyes.

### Animation strategy
Pure CSS transitions on all interactive states. Keyframe animations only for:
- Progress bar: subtle shimmer effect
- Modal: backdrop blur + fade-in
- Tree content: height-based smooth expand (via `max-height` transition since `height: auto` doesn't animate)

**Alternative considered**: JavaScript animation library. Rejected — adds dependency and complexity for what CSS handles natively.

### Inline styles preserved
All CSS stays in `<style>` blocks within each template. This keeps deployment simple (no static file serving, no cache invalidation). Templates already auto-generate if missing, so this pattern is intentional.

## Risks / Trade-offs

- **[Risk] Google Fonts CDN requires internet at first load.** → Mitigation: Font loads once then browser caches. App is already server-hosted. System font fallback renders immediately while web font loads (flash of unstyled text is acceptable).
- **[Risk] CSS custom properties not supported in IE11.** → Mitigation: OfflineU targets modern browsers. IE11 usage is negligible for a self-hosted tool.
- **[Trade-off] Inline CSS in each template causes duplication.** → Mitigation: Tokens at `:root` are shared. Component styles are intentionally per-template. A shared stylesheet would require a build step or Flask static serving, which adds complexity for a 3-template app.

## Open Questions

None. All design decisions are resolved above.
