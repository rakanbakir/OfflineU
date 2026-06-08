## 1. Establish design tokens in course_dashboard.html

- [x] 1.1 Add Inter font `<link>` to `<head>` (weights 400, 500, 600, 700)
- [x] 1.2 Add `:root` CSS custom property block with all color, spacing, typography, radius, shadow, and transition tokens
- [x] 1.3 Update global reset (`*`) and `body` to use token variables
- [x] 1.4 Replace all hardcoded hex colors in the stylesheet with token references

## 2. Restyle core components in course_dashboard.html

- [x] 2.1 Header: softer background, refined heading typography with proper weight and letter-spacing
- [x] 2.2 Navigation bar: updated background, link hover states with transition
- [x] 2.3 Buttons: rounded corners, consistent padding, hover/active/focus states, disabled styling
- [x] 2.4 Cards: refined background, border-left accent, improved padding, box-shadow on hover
- [x] 2.5 Inputs: updated background, focus ring with accent color, placeholder color

## 3. Polish the course tree in course_dashboard.html

- [x] 3.1 Tree header: refined background, hover transition, toggle button rotation animation
- [x] 3.2 Tree content: smooth expand/collapse via max-height transition
- [x] 3.3 Lesson items: updated colors, hover elevation with translateX, completed state refinement
- [x] 3.4 Lesson type badges: refreshed palette (video=#ef4444, audio=#a855f7, text=#64748b, quiz=#f59e0b, mixed=#10b981)

## 4. Enhance progress bar and last-accessed card

- [x] 4.1 Progress bar: gradient fill, subtle shimmer animation via keyframes, rounded ends
- [x] 4.2 Last-accessed card: refined background, better visual hierarchy for the "Continue" button

## 5. Polish the AI settings modal

- [x] 5.1 Modal overlay: backdrop blur + fade-in transition
- [x] 5.2 Modal card: smooth scale+fade entrance, refined form labels and inputs
- [x] 5.3 Modal footer: consistent button spacing, save status animation

## 6. Refresh the empty state (no course loaded view)

- [x] 6.1 Course selector: refined dashed border, better centering, improved input and button layout
- [x] 6.2 Instruction cards: updated visual style, improved list typography and spacing

## 7. Modernize lesson_view.html

- [x] 7.1 Add Inter font link and `:root` token block (same tokens as dashboard)
- [x] 7.2 Replace all hardcoded colors with token references
- [x] 7.3 Style media player container with refined borders and background
- [x] 7.4 Update navigation buttons, mark-complete button with consistent button tokens
- [x] 7.5 Style resource file links with hover transitions and improved layout

## 8. Modernize select_course.html

- [x] 8.1 Add Inter font link and `:root` token block (same tokens as dashboard)
- [x] 8.2 Replace all hardcoded colors with token references
- [x] 8.3 Update directory browser styling to match the dashboard tree component
- [x] 8.4 Style the course candidate highlight and loading states

## 9. Final verification

- [x] 9.1 Start the app with `python offenseu_core.py` and load a test course
- [x] 9.2 Verify all three templates render with the new design
- [x] 9.3 Verify tree expand/collapse animation is smooth
- [x] 9.4 Verify modal open/close animation is smooth
- [x] 9.5 Verify progress bar shimmer animation works
- [x] 9.6 Verify no visual regressions: all text readable, all buttons clickable, layout intact
