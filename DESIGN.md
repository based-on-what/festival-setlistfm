# Design System — Festival Setlist Creator

Direction: **festival poster editorial**. The lineup reads like a printed festival bill; controls stay quiet product UI. Two themes: light = poster paper with vermilion ink, dark = night bill with acid yellow. Color strategy: Committed (the accent carries the bill numbers, rules, and the create action; it is ink, not glow).

## Color

All values OKLCH, defined in `static/tokens.css`. No raw hex/oklch in `style.css`.

### Dark — "night bill" (default, `:root`)

| Token | Value | Role |
| --- | --- | --- |
| `--bg` | `oklch(14% 0.015 60)` | Warm charcoal page |
| `--surface` | `oklch(17% 0.018 60)` | Panels (search rail) |
| `--surface-2` | `oklch(20% 0.02 60)` | Inputs, rows |
| `--surface-3` | `oklch(25% 0.022 60)` | Hover, placeholders |
| `--text` | `oklch(93% 0.02 90)` | Warm off-white |
| `--muted` | `oklch(64% 0.03 80)` | Secondary text |
| `--border` | `oklch(93% 0.02 90 / 0.14)` | Hairlines |
| `--accent` | `oklch(86% 0.17 98)` | Acid yellow ink |
| `--on-accent` | `oklch(16% 0.02 60)` | Text on accent |
| `--danger` | `oklch(70% 0.19 28)` | Errors |
| `--success` | `oklch(80% 0.15 140)` | OK status |

### Light — "poster paper" (`[data-theme="light"]`)

| Token | Value | Role |
| --- | --- | --- |
| `--bg` | `oklch(95.5% 0.018 90)` | Warm paper |
| `--surface` | `oklch(98% 0.01 90)` | Panels |
| `--text` | `oklch(22% 0.025 50)` | Warm ink |
| `--accent` | `oklch(52% 0.2 32)` | Vermilion ink |
| `--on-accent` | `oklch(97% 0.012 90)` | Text on accent |

Same role table as dark; values in tokens.css.

## Typography

| Role | Font | Settings |
| --- | --- | --- |
| Bill / display | Archivo (variable) | `font-stretch` 62%, weight 800-900, uppercase, tracking -0.01em |
| UI text | Archivo | stretch 100%, weight 400-700, sentence case |
| Meta / numerals | Space Mono | indices (01, 02), counts (3/20), dates, statuses |

Loaded as one variable family: `family=Archivo:wdth,wght@62..125,100..900` + Space Mono 400/700. Display type appears ONLY on: page masthead, artist names in the lineup, result headline. Buttons, labels, hints, toasts use UI Archivo.

Scale (rem, fixed): 0.75 / 0.8125 / 0.875 (base UI) / 1 / 1.5 / clamp bill rows 1.375-2.25 / masthead 2.5-4.

## Layout

- App shell `max-width: 1060px`. Desktop (>= 880px): two-pane grid, left rail 320px (search, options, sticky), right pane = the bill (lineup + create). Mobile: single column, search then bill then options then create.
- The bill is open layout: no card border, rows separated by hairlines, numbered `01..100` in mono accent.
- Header is a masthead: oversized condensed wordmark + thin double rule (poster conceit), theme toggle right.
- Spacing scale: 4/8/12/16/24/32/48/64 (`--space-1..8`).
- Radii: controls 6px (`--radius-sm`), panels 10px (`--radius`). The bill itself has no radius (print edge).

## Components

All interactive components define: default, hover, focus-visible, active, disabled, loading.

- **Button**: `.btn` base; `.btn-primary` (accent block, on-accent text), `.btn-ghost` (hairline). Primary create button is the drenched moment: full-width accent slab with mono arrow.
- **Input**: `.input` on `--surface-2`, hairline border, accent focus ring (2px ring via box-shadow).
- **Combobox dropdown**: panel under search, skeleton shimmer rows while loading, mono meta line.
- **Bill row** (`.artist-item`): mono index + condensed uppercase name + swap handle + remove. Drag = lowered opacity; drop target = accent hairline.
- **Empty state**: dashed slot rows that look like an unprinted bill, teaches "search to add".
- **Build progress**: create button becomes live progress slab (`N/M artists`), `aria-busy`.
- **Toast**: bottom-right stack, tinted semantic backgrounds, progress hairline, max 5.
- **Result**: full-pane payoff: headline, per-artist mono ledger, warnings box, Spotify embed.

## Motion

150-250ms, `cubic-bezier(0.2, 0, 0, 1)`. State changes only: row enter (slide 4px), dropdown reveal, toast in/out, progress. No page-load choreography. `prefers-reduced-motion`: all animation off, skeleton static.
