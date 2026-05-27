# Frontend App Shell Design Spec

Date: 2026-05-27

## Decision Summary

Build a fresh teal learning workspace for study_agent before the next major product feature. The design should feel clean, focused, and modern, with teal as the primary product signal and lightweight motion used only to clarify interaction state. The page should remain a production tool, not a marketing landing page or playful education app.

This phase establishes the app shell and visual system that later route generation, chapter study, chat, quiz, and review pages will inherit.

## Design Direction

Name: Fresh Teal Learning Workspace.

The interface uses a light, calm background with teal accents. The core visual memory should be a clear workspace with a soft teal active rail, crisp cards, readable data, and restrained motion. The app should feel closer to NotebookLM and Sana than to a consumer course marketplace.

The design must avoid:

- Marketing hero layouts.
- Centered decorative showcase cards that do not match the user's next action.
- Large gradient blobs, particle backgrounds, or ornamental effects.
- Dark dashboard dominance.
- Childlike illustration-heavy education styling.
- Cards nested inside cards.
- UI text that explains how the UI works instead of presenting useful product data.

## Layout Model

The global layout has three zones:

```text
+----------------------------------------------------------------------------+
| Top bar: product, search, model/runtime status, user menu                   |
+---------------+----------------------------------------------+-------------+
| Sidebar       | Main task area                               | Right rail  |
| Spaces        | Continue learning / route / source workflow  | Today       |
| Library       |                                              | AI Mentor   |
| Reviews       | Supporting lists live below primary task      | Progress    |
| Progress      |                                              |             |
+---------------+----------------------------------------------+-------------+
```

The center is reserved for the user's primary task. On the dashboard this is "Continue Learning", not a decorative card grid. On a study space page this is the route, current chapter, source workflow, or next action. The right rail is for small supporting panels such as today's reviews, AI mentor suggestions, progress, and alerts.

On mobile, the sidebar collapses into a top navigation or compact drawer, the right rail stacks below the primary content, and action groups wrap without text overlap.

## Visual System

Use CSS variables in the global stylesheet so future pages can share the same tokens.

Core palette:

- Page background: `#f3fbf9`
- Surface: `#ffffff`
- Muted surface: `#ecfdf5`
- Border: `#cce7e1`
- Text primary: `#10201f`
- Text secondary: `#58706b`
- Primary teal: `#0f766e`
- Bright teal: `#14b8a6`
- Soft teal: `#ccfbf1`
- Success: `#16a34a`
- Warning: `#d97706`
- Error: `#dc2626`
- Info: `#2563eb`

Cards keep an 8px border radius, a subtle border, and a low shadow. Shadows should be barely visible at rest and more noticeable on hover. Teal should appear on selected state, focus rings, progress fills, primary buttons, and active navigation, not on every surface.

Typography should stay compact and readable. Use the existing system stack for now unless a later design pass explicitly introduces a production-safe font dependency. Do not scale font size with viewport width.

## Motion Rules

Motion is allowed, but it must support orientation and feedback:

- Page sections may enter with a subtle `fade + translateY(6px)` animation.
- Cards may lift by 1-2px on hover and slightly strengthen the border.
- Primary buttons may brighten and add a soft teal shadow on hover.
- Active sidebar item may show a small teal rail or glow.
- Progress bars may animate from 0 to their value once when rendered.
- Loading skeletons may use a gentle teal-tinted shimmer.

Motion must respect `prefers-reduced-motion: reduce`; in that mode transitions and animations are disabled.

Avoid continuous decorative animation unless it represents real state, such as loading, streaming, or processing.

## App Shell

The shell lives at `apps/web/app.vue` with shared styling in `apps/web/assets/css/main.css`.

Required elements:

- Sidebar with product name and primary navigation: Spaces, Library, Reviews, Progress, Settings.
- Top bar with search input, model/runtime status, and a static user menu affordance.
- Main content container with stable max width and responsive padding.
- Right rail support area where pages can opt in to supporting panels.

The sidebar should be light or white-tinted, not dark. It should use teal for the active navigation rail and hover state. The top bar should be compact and sticky only if it does not create layout issues.

## Shared Components Through CSS Classes

This phase does not need a full component library yet. It should define stable CSS classes that existing pages can adopt:

- `.primary-button`
- `.secondary-button`
- `.ghost-button`
- `.card`
- `.panel`
- `.status-badge`
- `.empty-state`
- `.error-alert`
- `.success-alert`
- `.form-field`
- `.input`
- `.textarea`
- `.select`
- `.metric-card`
- `.skeleton`
- `.page-enter`

Buttons must have visible focus states, disabled states, and stable height. Text inside buttons must not overflow on mobile.

## Dashboard Direction

The dashboard should not center decorative study-space cards as the main composition. It should prioritize resuming learning.

Structure:

- Header row: "Continue Learning", short subtitle, primary action "New Study Space".
- Primary continue panel: current or most recent active study space, next chapter/action, progress, and continue button.
- Recent spaces: compact grid below the continue panel.
- Right rail: due reviews, AI mentor suggestion, weekly progress.
- Empty state: single clean panel with a create action.

If there is no real data yet, use existing store data and graceful empty states. Do not invent fake production data in connected pages.

## Create Space Page Direction

The create flow should become a clear workspace form, not a plain document page.

Structure:

- Compact page heading.
- Three-step progress indicator.
- Form panel for name, goal, level, intensity, and target days.
- Source upload/import panel reserved for the existing upload work.
- Route draft panel reserved for AI render.
- Sticky or bottom action row on desktop; stacked actions on mobile.

The form should use teal focus rings and calm validation/error states.

## Study Space Detail Direction

The study space detail page should keep the source library work but visually align it with the new shell.

Structure:

- Space header with name/id, goal summary, progress summary affordance, and primary next action.
- Main column: route/current work area first, then source library.
- Source library keeps filters, upload metadata, ingestion actions, and chunk preview.
- Right rail: AI mentor status, ingestion health, next recommended study step.

The existing source library interactions must not regress:

- Upload `.txt` and `.md`.
- Presign, object upload, upload confirmation, source reload.
- Status filters and counts.
- Retry/re-run labels.
- Chunk preview empty action.
- Dev auth headers on protected API calls.

## Accessibility and Responsiveness

Required behavior:

- Keyboard focus visible on links, buttons, inputs, and file controls.
- Color is not the only status indicator; badges include text.
- Minimum interactive target height is 40px for normal buttons.
- Mobile layout must stack into a single readable column.
- Long file names, source names, IDs, and error messages wrap instead of overflowing.
- `prefers-reduced-motion` disables non-essential animation.

## Testing Expectations

Add or update frontend tests around behavior, not visual pixels:

- App shell renders primary navigation and top bar.
- Dashboard renders create action and handles empty/non-empty spaces.
- Create-space page still renders the AI render and submit controls.
- Study-space source library tests continue to pass.

For visual QA, use the browser after implementation and check:

- Desktop dashboard.
- Mobile dashboard.
- Create-space page.
- Study-space detail with source library.

## Out of Scope

- Full component extraction into a package.
- Installing a UI framework.
- Dark mode.
- Real auth UI.
- Real global search behavior.
- Route generation implementation.
- Chapter chat redesign.
- Complex animation libraries.

## Acceptance Criteria

- The app has a coherent fresh teal visual language across existing pages.
- The shell gives the product a real workspace structure: sidebar, top bar, main area, and optional support rail.
- Existing study-space creation and source-library tests still pass.
- Motion is present but restrained and disabled under reduced-motion preference.
- The center area prioritizes the user's learning task, not decorative cards.
- The implementation remains small enough to review in one PR.
