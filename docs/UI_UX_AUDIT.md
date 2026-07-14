# AiOS UI/UX Audit

Date: 2026-07-12

Scope: every server-rendered AiOS desktop screen, its shared navigation, forms,
tables, feedback states, and responsive behavior. This audit intentionally does
not propose workflow or business-logic changes.

## Executive assessment

AiOS has a recognizable visual identity and usable local-first workflows, but it
does not yet feel like one finished desktop product. The strongest issues are
systemic: the same components use multiple radii and heights, page headers are
far too large for a work surface, the sidebar exposes too many equal-weight
destinations, feedback states are mostly plain text, and dense tools such as the
command planner inherit styling designed for lightweight cards.

The current CSS is a 45 KB accumulation of page styles with repeated selectors.
Every full-page template repeats document and shell markup. These two facts make
small visual fixes drift across screens. The refactor should therefore begin at
the token and shared-component layer, then resolve page-specific exceptions.

## Severity scale

- P0: blocks use or hides important data.
- P1: materially harms navigation, readability, accessibility, or trust.
- P2: visible inconsistency or avoidable friction.
- P3: polish opportunity.

## Global findings

| Area | Severity | Finding | Required outcome |
| --- | --- | --- | --- |
| Typography | P1 | Global `h1` reaches 72 px with a 0.98 line-height, which overwhelms desktop tools and wraps aggressively at laptop widths. | Use the documented 32/40 page-title token and a 24/32 section-title token. |
| Layout | P1 | Shell, heroes, panels, stat cards, and page-specific cards use unrelated padding and radius values from 12 to 30 px. | Align all surfaces to the 8 px spacing grid and three radius tokens. |
| Navigation | P1 | Fifteen sidebar destinations have equal weight in a narrow, scrolling rail; the top rail duplicates five of them. | Group destinations visually, keep active and hover states consistent, and preserve labels at every desktop width. |
| Forms | P1 | Inputs, selects, textareas, and buttons do not share one 44 px control contract; several placeholder-only dashboard/mobile fields lack persistent labels. | Standardize controls and add accessible names or visible labels to every field. |
| Buttons | P1 | `.ghost-button` is 34 px while global buttons are 42 px; link buttons and form buttons vary in treatment. Disabled states are not visually complete. | Use 44 px default and 36 px compact variants, with unified hover, focus, pressed, busy, and disabled states. |
| Tables | P1 | Command Planner places full editing forms inside a ten-column table. It requires horizontal scrolling and creates extremely tall rows. | Keep the workflow, but make the table legible with sticky headers, stable column widths, compact controls, and clear horizontal-scroll affordance. |
| Errors | P1 | Errors are injected as red-tinted text panels. There is no friendly title, recovery guidance, expandable detail, retry, back, copy, or report action. | Introduce a reusable error-state component and a safe global error page. |
| Empty states | P2 | Empty states share a generic `Next step` prefix and usually omit a direct action or example. | Use contextual icon, explanation, primary action, optional secondary action, and example where the route supports it. |
| Loading | P1 | Forms get a busy flag, but initial data loading and live refresh use text rather than skeletons or progress. | Add reusable skeletons and an accessible live loading indicator; preserve reduced-motion behavior. |
| Accessibility | P1 | Focus rings exist, but contrast varies, icon-only meaning is inconsistent, native status color is sometimes the only signal, and some fields are placeholder-only. | Meet WCAG AA contrast, retain text labels, use 44 px targets, and add reduced-motion and forced-colors support. |
| Motion | P2 | Every panel animates into view, creating excessive movement on long dashboards. | Animate page-level transitions and direct interactions only; disable nonessential motion when requested. |
| Responsiveness | P1 | At 1100 px the entire sidebar becomes a long horizontal strip, while the top rail remains another horizontal strip. This consumes vertical space and obscures navigation. | Use a compact desktop rail through laptop sizes and a single mobile navigation pattern below tablet width. |
| Performance | P2 | Many panels receive backdrop blur, large shadows, and entrance animations. | Limit blur/elevation to shell chrome and overlays; keep content surfaces opaque and stable. |
| Code structure | P1 | Full HTML shell is duplicated across 16 desktop templates and component definitions are repeated in one large stylesheet. | Establish shared tokens/components now, then migrate templates to one layout without changing route behavior. |

## Screen inventory

| Screen | Current strengths | Problems found | Priority |
| --- | --- | --- | --- |
| Login | Focused single task, clear PIN purpose. | Card and input hierarchy do not match the desktop shell; error is plain text; no show/hide affordance or recovery guidance. | P1 |
| Dashboard | Useful summary, live data, clear top-level metrics. | Hero dominates first viewport; two navigation systems compete; mixed light summary panel breaks the dark visual language; cards use several unrelated styles; test-email form lacks persistent labels. | P1 |
| Mobile dashboard | Dedicated compact view and bottom navigation. | Quick-capture fields rely on placeholders; desktop color/elevation rules leak into mobile; loading and empty actions are weak. | P1 |
| Gmail / Hackathons / Jobs / Wellbeing pipelines | Shared template is a good reuse point. | Generic cards do not distinguish records, run history, and metrics; long values wrap unpredictably; no filter/loading skeleton. | P2 |
| Memory | Search-first workflow is strong. | Search field has no visible label; graph and project cards have inconsistent density; raw error panel; long checkpoint form lacks grouping and helper text. | P1 |
| Goal Planner | Good plan hierarchy and progress concept. | Roadmap form sits inside a hero; nested task cards are dense; session fields rely on placeholders; progress and status colors need semantic consistency. | P1 |
| Command Planner | Powerful unified planning surface. | Ten-column editable table is the highest-risk responsive surface; forms inside rows are too tall; sticky header, overflow cue, compact density, and cell truncation are incomplete. | P0 |
| Automation | Safety boundary is clearly communicated. | Command form is visually heavy; risk/status chips are inconsistent; run history needs stronger grouping and recoverable error states. | P2 |
| Browser Agent | Safety lock and staged application workflow are clear. | Hero contains too many fields; status tokens use inconsistent language/colors; opportunities need a stable card grid and better empty action. | P2 |
| Career Copilot | Logical feature grouping and evidence cards. | Four major forms compete at once; results use raw `pre` overflow; card heights and text density vary; no progressive disclosure for secondary tools. | P1 |
| Sources | Simple import workflow. | File control and progress feedback are visually weak; unsupported-type errors are plain result panels; pipeline status lacks clear hierarchy. | P2 |
| Connectors | Account state and manual run actions are available. | Repeated run buttons lack busy/success feedback; setup-required messaging is dense; disabled state needs explanation and tooltip. | P1 |
| Workers | Direct control and status are present. | Start/stop actions have equal emphasis; errors appear inline without remediation; status presentation depends heavily on color. | P1 |
| Settings | Comprehensive local controls and account management. | Very long single page; repeated panels lack section navigation; switches are visually checkbox-like; save actions are not anchored to their section; success feedback is detached. | P1 |
| Profile | Compact identity editor. | Image fallback has an empty alt; form hierarchy and save feedback need shared state components. | P2 |

## Dialog and state audit

The application currently has no reusable modal/dialog primitive. Native
`details` elements are used for progressive disclosure in Planner and Browser
Agent. Keep those interactions, but standardize their summary row, focus state,
expanded surface, and motion.

There is no dedicated 404/500 template. Normal users can therefore receive
framework-style failures in exceptional paths. Add friendly 404 and 500 pages
with expandable technical details, retry/back/copy/report actions, while keeping
stack traces out of the rendered response.

Loading behavior is limited to JavaScript changing submit-button state. There
are no dashboard, list, table, or page skeleton primitives. Empty states are
present on most data surfaces but are generic and action-poor.

## Measurable acceptance criteria

- All desktop pages use the same page-title, section-title, body, small, and
  caption tokens.
- Default controls are 44 px high; compact controls are at least 36 px; icon-only
  controls retain a 44 px target.
- Every keyboard-focusable control has a visible focus indicator.
- Every form field has a programmatic accessible name, and important forms keep
  visible labels after entry.
- No viewport from 768 to 1920 CSS pixels has document-level horizontal overflow.
- The command-planner table may scroll inside its own labeled region, with a
  sticky header and no clipped controls.
- Light text, muted text, success, warning, and danger colors meet readable
  contrast on their intended surfaces.
- Reduced-motion mode removes page/panel translation and nonessential animation.
- Every empty, error, and loading state uses a shared component style.
- All existing routes, forms, and service behavior remain unchanged.

## Post-refactor verification

Completed on 2026-07-12 after the shared design-system layer was applied.

- All 17 rendered routes were opened at a 1024 x 768 CSS-pixel viewport.
- No route produced document-level horizontal overflow.
- No visible interactive target was shorter than 34 px; primary controls use
  the 44 px design token and compact controls use 36 px.
- Runtime inspection found no unnamed inputs, selects, textareas, or buttons.
- The command planner contains its 1440 px table inside an independently
  scrollable region with a sticky header; the document itself does not overflow.
- Dashboard and page titles resolve to 32 px rather than the former 72 px scale.
- Panels and repeated cards resolve to the shared 16 px radius.
- The 1024 px shell resolves to a 76 px compact navigation rail with named
  tooltips and an icon-based lock control.
- Empty states are enhanced on initial render and after live sync with an icon,
  title, explanation, contextual primary action, dashboard action, and example.
- 404 and 500 errors render the shared recovery page without exposing stack
  traces. The page includes retry, back, dashboard, copy, and report actions.
- Memory search uses a skeleton loading state and form submissions expose busy
  state through both animation and `aria-busy`.
- Browser console inspection reported no errors after the route audit.
- All 13 desktop content templates now inherit `base.html`; document metadata,
  skip navigation, shell chrome, styles, main landmark, transition indicator,
  and scripts have one owner.
- Standalone login now uses a persistent PIN label, the shared 16 px surface,
  44 px controls, inline validation, and submission progress feedback.
- Settings now provides sticky in-page navigation across readiness, startup,
  AI/connectors, accounts, diagnostics, and privacy.
- Runtime audits at 1920 x 1080, 1440 x 900, 1024 x 768, 768 x 900, and
  390 x 844 found no document overflow or clipped controls. The dedicated
  mobile dashboard also had no visible target below 34 px.
- Core text, muted text, accent text, danger text, and inverse primary-button
  token pairs are protected by WCAG AA contrast regression tests.
