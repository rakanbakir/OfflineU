## Why

The current OfflineU UI is functionally complete but visually dated. It relies on basic system fonts, a flat grayscale palette, minimal transitions, and inconsistent spacing. A modern visual refresh will make the app feel more polished, engaging, and professional — improving the learning experience without changing any functionality.

## What Changes

- Replace system font stack with a modern, readable web font via CDN
- Introduce a cohesive color system with CSS custom properties (tokens) for consistency
- Refine the dark theme palette: softer backgrounds, higher contrast text, distinct accent colors for video/audio/text/quiz types
- Improve spacing and typographic hierarchy (larger headings, better line-height, consistent padding)
- Add subtle animations: tree toggle transitions, card hover elevation, lesson item entrance
- Polish the empty state ("Select a Course") with better visual structure and callouts
- Enhance the progress bar with a gradient and subtle animation
- Standardize button styles with rounded corners, consistent padding, and hover/active states
- Add a subtle background pattern or gradient to the page body
- Improve the AI settings modal with backdrop blur and smoother open/close animations

## Capabilities

### New Capabilities
<!-- No new functional capabilities — purely visual refresh -->

### Modified Capabilities
<!-- No existing specs to modify -->

## Impact

- Affected files: `templates/course_dashboard.html`, `templates/lesson_view.html`, `templates/select_course.html`
- All changes are CSS-only (and a single font import from Google Fonts)
- No Python code changes required
- No API changes, no new dependencies, no breaking changes
