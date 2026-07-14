# AiOS Design System

AiOS uses a calm dark workspace with a restrained acid-lime accent. Lime is for
selection and primary action, not a background wash. Content surfaces stay
neutral so emails, plans, repositories, and status data remain easy to scan.

## Foundations

### Typography

| Token | Size / line height | Weight | Use |
| --- | --- | --- | --- |
| Display | 40 / 48 | 700 | Login or exceptional empty state only |
| H1 | 32 / 40 | 700 | Page title |
| H2 | 24 / 32 | 650 | Section title |
| H3 | 18 / 26 | 650 | Card title |
| Body large | 16 / 26 | 400 | Introductory copy |
| Body | 14 / 22 | 400 | Primary interface text |
| Small | 13 / 20 | 400 | Secondary text |
| Caption | 12 / 16 | 600 | Labels and metadata |

The UI font stack is Inter, `Segoe UI`, and system sans-serif. Code and paths use
JetBrains Mono, `Cascadia Code`, and system monospace.

### Spacing

Use only `4, 8, 12, 16, 20, 24, 32, 40, 48, 64` CSS pixels. Standard page gap is
20 px, panel padding is 20 px, and dense row padding is 12 px 16 px.

### Radius

- Small: 8 px for tags and compact controls.
- Medium: 12 px for buttons, inputs, rows, and menus.
- Large: 16 px for cards, panels, and dialogs.
- Pill: 999 px only for status chips, avatars, and segmented controls.

### Elevation

- Surface: border plus opaque neutral background; no shadow.
- Raised: `0 12px 32px rgba(0, 0, 0, .24)` for sticky chrome and selected tools.
- Overlay: `0 24px 64px rgba(0, 0, 0, .42)` for dialogs and menus.

## Color roles

- Background: `#090b09`
- Sidebar: `#0d100d`
- Surface: `#121512`
- Surface raised: `#181c18`
- Border: `#293029`
- Text: `#f4f7f2`
- Muted: `#a7b0a4`
- Primary: `#a7ff3c`
- Primary hover: `#b8ff63`
- Information: `#75d7ff`
- Success: `#72e6a2`
- Warning: `#ffd166`
- Danger: `#ff7b86`

Semantic colors always accompany text or icon meaning. They are never the only
status signal.

## Components

### Buttons

Default height is 44 px, compact height is 36 px. Variants are primary,
secondary, ghost, danger, success, and icon. All variants share radius,
padding, focus ring, pressed transform, busy state, and disabled opacity.

### Forms

Labels remain visible above fields. Input, select, and date controls are 44 px;
textareas start at 96 px. Helper and inline-error text sits below the field. A
form uses 16 px row gaps and 20 px section gaps. Checkbox and switch labels have
a minimum 44 px target.

### Cards and panels

Panels use the large radius, 20 px padding, a neutral opaque surface, and a
single border. Repeated item cards use the medium radius and 16 px padding.
Cards do not nest another decorative card unless the inner element is a distinct
interactive record.

### Tables

Tables have 44 px sticky headers, 48 px minimum rows, left-aligned text, stable
column widths, and a row hover color. Dense editable tables use compact controls
and scroll inside a labeled container. Cell text wraps at natural boundaries and
long URLs use ellipsis with the full value available on focus or hover.

### Feedback

- Empty: contextual icon, short title, explanation, primary action, optional
  secondary action, and an example when useful.
- Loading: skeleton matching the final geometry, plus an `aria-live` status.
- Error: friendly title, explanation, suggested fix, retry and back actions,
  expandable technical detail, copy-error, and report-issue action.
- Toast: concise success or failure confirmation; never the only record of an
  important action.

## Responsive behavior

- Large desktop: above 1440 px, content maxes at 1600 px.
- Desktop: 1025 to 1440 px, persistent 232 px sidebar and two-column content.
- Tablet/laptop: 769 to 1024 px, compact 76 px icon rail with labels exposed by
  accessible tooltip; content becomes one column.
- Mobile: 768 px and below, desktop shell collapses to a single top/bottom
  navigation pattern and cards use 16 px gutters.

No typography scales continuously with viewport width. Breakpoint changes are
discrete and predictable.

## Motion

- Fast feedback: 140 ms for buttons, tabs, and navigation presses.
- Standard transitions: 240 ms for hover depth and selection changes.
- Expressive entrance: 420 ms for page sections, capped at seven stagger steps.
- Entrances use `cubic-bezier(0.2, 0.8, 0.2, 1)` and never delay an action.
- Live values crossfade only when their content changes.
- `prefers-reduced-motion` removes transforms, staggering, and looping effects.
