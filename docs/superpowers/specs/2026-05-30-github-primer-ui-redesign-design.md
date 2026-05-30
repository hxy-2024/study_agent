# GitHub Primer UI Redesign Design

## Design Read

Study Agent is a local-first AI learning operating system for a single power user. The interface should feel closer to GitHub Dashboard, Primer, Codex, and a quiet developer tool than to a marketing site, generic SaaS dashboard, or notebook app.

The visual language is compact, neutral, row-based, and functional. AI autonomy is shown through recommendations, activity rows, and prepared actions, not through decorative gradients or runtime-debug panels exposed in the core learning flow.

## Visual System

- Background: Primer-like canvas, `#f6f8fa`.
- Primary surface: white panels with thin `#d0d7de` borders.
- Text: near-black `#24292f`; secondary text `#57606a`.
- Accent colors: GitHub blue for navigation/action links, GitHub green for primary actions, red only for destructive actions.
- Radius: 6px for regular controls and panels, 10-14px only for floating overlays and chat composer.
- Shadows: no shadows on normal page sections; use shadows only for floating panels, drawers, modals, popovers, and right-side overlays.
- Motion: fast, low-distance transitions for drawer/panel open, hover rows, sidebar collapse, select controls, and send/interrupt buttons.

## Global App Shell

The global shell appears on every page:

- Top bar with hamburger button, product mark, product name, search area or page context, compact navigation, and local user avatar.
- Navigation drawer is a floating overlay with rounded corners, border, and shadow. Its first item is Home and always navigates to `/`.
- Settings and runtime status remain available, but use Primer-like modal/drawer surfaces.
- No decorative page backgrounds, gradient blobs, or hero-style sections.

## Home Dashboard

Home is modeled after GitHub Dashboard:

- Left column lists all active study spaces with a search field and green New button.
- Study spaces are rows separated by borders, not individual cards.
- Rows show name, goal, and a small Continue/Study/Review action.
- Hover reveals a red trash icon for delete.
- Main column shows an activity/recommendation feed, using rows with dividers.
- Top of main column gives current page title, short agent recommendation context, and compact actions.
- Right column shows calendar and today agenda/event rows.
- Main Agent content is presented as activity/recommendation rows or a floating conversation panel, not as a large nested card in the default view.
- Archived spaces use a collapsible/secondary row section rather than a large panel.

## Create Learning Space

Create space becomes a focused workspace:

- Back arrow in the top-left of the page content.
- Main content uses two columns: left setup/ingestion workflow, right sticky route outline.
- Form sections are divided by headings and separators instead of stacked cards.
- File upload, paste text, model, and embedding settings remain visible in sequence.
- The route outline is a sticky side panel with a thin border and no heavy shadow.
- Embedded chunks are hidden by default and shown in a centered floating modal with border, radius, and shadow.
- Generated chapter details appear in a larger centered floating modal with left chapter list and right detail panel.
- AI-rendered route text can use a restrained blue/green gradient only for the AI Render label or generated-state marker, not for large body text.

## Chapter Study Page

The chapter page is the primary learning workspace:

- Outer page fits within one viewport on desktop.
- Left chapter rail lists all chapters and can collapse smoothly; the chat area expands when collapsed.
- Main column is the chat workspace with a compact breadcrumb, quiz action, scrollable message thread, and bottom composer.
- Right session/notes/progress panel is a floating overlay-style panel with rounded corners and a real shadow.
- The chat thread, not the outer page, owns vertical scrolling.
- Composer uses a Codex-like input surface: plus attachment icon, model select, thinking select, and green send button.
- During AI generation, send becomes a red square interrupt button.
- Web search is not a frontend toggle; backend tools decide usage.
- MCP UI is hidden from the default learning interface.
- Fork checkpoint is an icon-only action.
- Diagnostic surfaces such as Chapter state, Chapter runtime, Source evidence, Space planner, Action queue, and Agent runtime do not appear in the learning interface.

## Quiz Page

The quiz page follows the same Primer-like layout:

- Top title area is a simple row, not a hero/card.
- Questions are stacked as bordered sections with row-based options.
- Selected wrong answers use soft red background.
- Correct answers use stronger green background.
- Result summary is compact and uses separators, not a large card stack.
- Titles and question text strip markdown heading markers.

## Implementation Constraints

- Preserve endpoint URLs, auth headers, request bodies, route targets, and generated data flow.
- Preserve existing `data-testid` hooks unless tests are intentionally updated.
- Copy cleanup is allowed where text is visibly broken or mojibake, but it must be reflected in tests.
- Do not add a new UI library. The current Nuxt/Vue app has no component library; use scoped Vue and shared CSS.
- Do not introduce large images or decorative assets for this local developer-tool product.
- Keep `.superpowers/` brainstorm artifacts out of committed code.

## Success Criteria

- The app reads as one cohesive GitHub/Primer-inspired product system.
- The home page no longer looks like stacked cards.
- Create space has a focused two-column workflow and professional floating modals.
- Chapter study feels like a modern AI workspace with inner chat scrolling and floating context panel.
- Quiz page matches the same system.
- Existing core flows still pass: create space, ingest material, generate route, enter chapter, chat, notes, quiz, complete chapter, continue study.
