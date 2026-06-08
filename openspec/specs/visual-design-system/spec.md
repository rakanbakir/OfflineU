# Visual Design System

## Purpose

Defines the visual design system for OfflineU: CSS custom property tokens, dark color palette, typography, component styling conventions, animation standards, and lesson type categorization. Ensures visual consistency across all templates.

## Requirements

### Requirement: Design Token System
The application SHALL define all visual properties through CSS custom properties (`:root`) for consistent theming across all templates.

#### Scenario: Token categories
- **WHEN** a template stylesheet is loaded
- **THEN** `:root` SHALL contain tokens for colors (`--color-*`), typography (`--font-*`), spacing (`--space-*`), border radii (`--radius-*`), shadows (`--shadow-*`), and transitions (`--transition-*`)

#### Scenario: Cascade propagation
- **WHEN** a token value is changed in `:root`
- **THEN** all components referencing that token SHALL update without individual rule changes

### Requirement: Modern Typography
The application SHALL use the Inter typeface loaded from Google Fonts with a system font fallback stack.

#### Scenario: Font loading
- **WHEN** the application loads in a browser
- **THEN** text SHALL render in Inter (weights 400, 500, 600, 700) with fallback to `system-ui, -apple-system, sans-serif`

#### Scenario: Font smoothing
- **WHEN** text is rendered
- **THEN** `-webkit-font-smoothing: antialiased` and `-moz-osx-font-smoothing: grayscale` SHALL be applied to the body

### Requirement: Dark Color Palette
The application SHALL use a cohesive deep slate dark color scheme.

#### Scenario: Background hierarchy
- **WHEN** a page is rendered
- **THEN** body background SHALL be `#0f1117`, card surfaces SHALL be `#1a1d27`, elevated elements SHALL be `#22262f`

#### Scenario: Text contrast
- **WHEN** text is displayed
- **THEN** primary text SHALL be `#e4e6ed`, secondary text SHALL be `#8b8fa3`, muted text SHALL be `#5b5f6b`

#### Scenario: Accent colors
- **WHEN** interactive elements are styled
- **THEN** primary accent SHALL be `#3b82f6` (blue), success indicator SHALL be `#22c55e` (green)

### Requirement: Component Consistency
All shared UI components (buttons, cards, inputs, modals, progress bar, tree items) SHALL use consistent visual tokens.

#### Scenario: Button states
- **WHEN** a button is rendered
- **THEN** it SHALL have rounded corners (`6px`), consistent padding, a hover state with darker accent color, and an active state with scale-down effect

#### Scenario: Card visual
- **WHEN** a card is rendered
- **THEN** it SHALL have a left-accent border, background from the surface token, and a subtle box-shadow on hover

#### Scenario: Input focus
- **WHEN** an input receives focus
- **THEN** its border color SHALL change to the accent color and a focus ring SHALL appear

### Requirement: Smooth Animations
Interactive elements SHALL use CSS transitions for state changes, not jump cuts.

#### Scenario: Tree expand/collapse
- **WHEN** a tree node is toggled
- **THEN** child content SHALL smoothly expand via `max-height` transition over approximately 400ms

#### Scenario: Modal entrance
- **WHEN** the AI settings modal opens
- **THEN** the overlay SHALL fade in with backdrop blur, and the modal card SHALL scale+fade into view over approximately 250ms

#### Scenario: Progress bar shimmer
- **WHEN** the progress bar is visible
- **THEN** the fill SHALL have a subtle gradient shimmer animation playing continuously

### Requirement: Lesson Type Visual Categorization
Lesson type badges SHALL use distinct, recognizable colors.

#### Scenario: Badge rendering
- **WHEN** a lesson item is displayed
- **THEN** video badges SHALL be red (`#ef4444`), audio badges SHALL be purple (`#a855f7`), text badges SHALL be slate (`#64748b`), quiz badges SHALL be amber with dark text (`#f59e0b`), and mixed badges SHALL be emerald (`#10b981`)
