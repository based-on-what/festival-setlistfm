# Production UI System — Design Spec

**Date:** 2026-05-29
**Scope:** Token system, toast overhaul, skeleton loader, polish pass
**Visual direction:** Amplified Terminal (OKLCH, same bones, punchier glow)
**CSS architecture:** `tokens.css` + `style.css` split

---

## 1. File Architecture

| File | Status | What changes |
|------|--------|--------------|
| `static/tokens.css` | NEW | All OKLCH design tokens. Single source of truth for both themes. |
| `static/style.css` | MODIFIED | Consume tokens. Remove inline hex. Fix toast side-stripe. Spacing rhythm. |
| `static/components/skeleton.js` | NEW | `SkeletonLoader` factory. Renders shimmer rows into dropdown during search. |
| `static/components/dropdown.js` | MODIFIED | Add `showSkeleton()` / `hideSkeleton()` methods. Remove input spinner dependency. |
| `static/components/toast.js` | NO CHANGE | Side-stripe is CSS-only. JS unchanged. |
| `static/components/artist-item.js` | MODIFIED | Drag handle gets proper `aria-label`. |
| `templates/index.html` | MODIFIED | Add `<link>` for `tokens.css`. Remove `#search-spinner` div. |
| `static/store.js`, `static/app.js`, `static/components/utils.js` | UNCHANGED | No changes needed. |

---

## 2. Design Tokens (`tokens.css`)

Full OKLCH palette. No hex values. All neutrals tinted toward hue 145 (the green channel) at chroma 0.01–0.02 — imperceptible tint, prevents dead grey.

### Dark theme (`:root`)

```css
/* Surfaces */
--bg:          oklch(9%  0.012 145);
--surface:     oklch(11% 0.014 145);
--surface-2:   oklch(14% 0.015 145);
--surface-3:   oklch(17% 0.016 145);

/* Borders */
--border:      oklch(30% 0.15 136 / 0.28);

/* Accent (neon green) */
--accent:       oklch(92% 0.28 136);
--accent-hover: oklch(86% 0.26 136);
--accent-glow:  oklch(92% 0.28 136 / 0.30);

/* Text */
--text:  oklch(88% 0.018 145);
--muted: oklch(42% 0.04  145);

/* Semantic */
--danger:  oklch(65% 0.22 25);
--success: oklch(78% 0.22 145);

/* Toast semantic backgrounds */
--toast-error-bg:      oklch(14% 0.04 25);
--toast-error-border:  oklch(28% 0.10 25);
--toast-success-bg:    oklch(13% 0.04 145);
--toast-success-border:oklch(28% 0.10 145);
--toast-warning-bg:    oklch(14% 0.04 75);
--toast-warning-border:oklch(28% 0.10 75);
--toast-info-bg:       oklch(12% 0.02 145);
--toast-info-border:   oklch(24% 0.05 145);
--toast-warning-fg:    oklch(78% 0.18 75);
--toast-info-fg:       oklch(60% 0.08 220);

/* Warning box (in-page) */
--warning-bg:     oklch(14% 0.04 75);
--warning-fg:     oklch(78% 0.18 75);
--warning-border: oklch(28% 0.10 75);

/* Spacing scale */
--space-1: 4px;
--space-2: 8px;
--space-3: 12px;
--space-4: 16px;
--space-5: 24px;
--space-6: 32px;
--space-7: 48px;

/* Radii */
--radius:    12px;
--radius-sm: 8px;

/* Transitions */
--ease-out: cubic-bezier(0.2, 0, 0, 1);
--t-fast:   150ms cubic-bezier(0.2, 0, 0, 1);
--t-base:   220ms cubic-bezier(0.2, 0, 0, 1);

/* Skeleton animation */
--skeleton-base:  oklch(16% 0.01  145);
--skeleton-shine: oklch(20% 0.015 145);
```

### Light theme (`[data-theme="light"]`)

```css
--bg:           oklch(96% 0.008 145);
--surface:      oklch(100% 0.005 145);
--surface-2:    oklch(93%  0.008 145);
--surface-3:    oklch(88%  0.01  145);
--border:       oklch(55%  0.18  25 / 0.30);
--accent:       oklch(48%  0.22  25);
--accent-hover: oklch(42%  0.22  25);
--accent-glow:  oklch(48%  0.22  25 / 0.25);
--text:         oklch(16%  0.02  145);
--muted:        oklch(55%  0.04  145);
--danger:       oklch(45%  0.22  25);
--success:      oklch(45%  0.18  145);

/* Toast backgrounds — light theme */
--toast-error-bg:      oklch(98% 0.015 25);
--toast-error-border:  oklch(80% 0.12  25);
--toast-success-bg:    oklch(97% 0.015 145);
--toast-success-border:oklch(75% 0.12  145);
--toast-warning-bg:    oklch(98% 0.015 75);
--toast-warning-border:oklch(78% 0.10  75);
--toast-info-bg:       oklch(97% 0.008 220);
--toast-info-border:   oklch(75% 0.08  220);
--toast-warning-fg:    oklch(42% 0.14  75);
--toast-info-fg:       oklch(38% 0.10  220);

/* Warning box — light theme */
--warning-bg:     oklch(98% 0.015 75);
--warning-fg:     oklch(42% 0.14  75);
--warning-border: oklch(78% 0.10  75);

/* Skeleton — light theme */
--skeleton-base:  oklch(90% 0.008 145);
--skeleton-shine: oklch(96% 0.005 145);
```

---

## 3. Toast Overhaul

### What changes

Remove `border-left: 3px solid` (side-stripe — banned pattern).
Replace with per-variant `background` tint + full `border` (1px, all sides) + icon color.

### New CSS rules (in `style.css`)

```css
.toast--error   { background: var(--toast-error-bg);   border-color: var(--toast-error-border); }
.toast--success { background: var(--toast-success-bg); border-color: var(--toast-success-border); }
.toast--warning { background: var(--toast-warning-bg); border-color: var(--toast-warning-border); }
.toast--info    { background: var(--toast-info-bg);    border-color: var(--toast-info-border); }

.toast--error   .toast__icon { color: var(--danger); }
.toast--success .toast__icon { color: var(--success); }
.toast--warning .toast__icon { color: var(--toast-warning-fg); }
.toast--info    .toast__icon { color: var(--toast-info-fg); }
```

The progress bar stays. The JS `Toast` class is untouched.

---

## 4. Skeleton Loader (`skeleton.js`)

### API

```js
import { SkeletonLoader } from './components/skeleton.js';

const sk = new SkeletonLoader(containerElement, { count: 3 });
sk.show();   // renders shimmer rows into container, opens it
sk.hide();   // removes rows, closes container
```

### Implementation contract

- `show()` clears container, appends `count` shimmer items, removes `hidden` class
- `hide()` clears container, adds `hidden` class
- Each item: avatar circle + two lines (55% wide name, 35% wide meta)
- Shimmer via CSS `@keyframes shimmer` using `--skeleton-base` and `--skeleton-shine` tokens
- No JS animation — CSS only, respects `prefers-reduced-motion`

### Integration in `dropdown.js`

- Constructor receives optional `skeletonCount = 3`
- New public method `showSkeleton()` — calls `sk.show()`, also calls `this.open()` so dropdown is visible
- New public method `hideSkeleton()` — calls `sk.hide()`
- `render()` always calls `hideSkeleton()` first

### Integration in `app.js`

**Error paths:** `dropdown.render()` hides the skeleton on success. On all early-return paths that skip `render()`, call `dropdown.hideSkeleton()` explicitly:

```js
async function searchArtists(q) {
  dropdown.showSkeleton();
  try {
    const res  = await fetch(`/api/search-artist?q=${encodeURIComponent(q)}`);
    const data = await res.json();
    if (!res.ok || data.error) {
      dropdown.hideSkeleton();           // explicit: error early-return
      Toast.error(friendlyError(data.error, 'Artist search failed. Try again.'));
      return;
    }
    dropdown.render(data.artists || []); // hideSkeleton called inside render()
  } catch {
    dropdown.hideSkeleton();             // explicit: network error
    Toast.error('Network error. Check your connection and try again.');
  }
}
```

`#search-spinner` div and `.spinner` in search box removed entirely.

---

## 5. Polish Pass

### `artist-item.js`

Drag handle span gets `aria-label`:

```js
aria-label="Drag to reorder ${artist.name}"
```

### `index.html`

- Remove `<div id="search-spinner" ...>`
- Add `<link rel="stylesheet" href="/static/tokens.css" />` before `style.css`
- Theme toggle: add `aria-pressed` attribute, updated on toggle

### `app.js`

- Theme toggle: set `aria-pressed="true"/"false"` on state change
- Remove `searchSpinner` DOM ref and its usages
- `dropdown.showSkeleton()` before fetch, `dropdown.render()` handles hide on success

### `style.css` spacing

All `padding: 24px` on `.card` replaced by `var(--space-5)`.
All `margin-bottom: 16px` gaps replaced by `var(--space-4)`.
All hardcoded hex colors replaced by corresponding token var.

### Empty state

```html
<div class="empty-state-ring" aria-hidden="true">⠿</div>
<p class="empty-state-text">Search above to add artists.</p>
<p class="empty-state-hint">Up to 10 artists per playlist.</p>
```

New `.empty-state-hint` class: same as `.empty-state-text` but uses `--muted` color, slightly smaller font.

---

## 6. What Does NOT Change

- `ArtistStore` — no changes
- `SearchDropdown` keyboard navigation — no changes
- Drag-and-drop logic in `app.js` — no changes
- `createArtistItem` structure — only `aria-label` addition on drag handle
- `Toast` JS class — no changes
- All existing ARIA attributes — kept as-is

---

## 7. Acceptance Criteria

- [ ] No hex color values remain in `style.css` or `index.html`
- [ ] `tokens.css` is the sole color/spacing source of truth
- [ ] Zero `border-left` accent stripes on toasts
- [ ] Skeleton renders in dropdown during a real search request
- [ ] Skeleton closes on both success and error paths
- [ ] All interactive elements have visible `:focus-visible` outline using `--accent`
- [ ] `prefers-reduced-motion` suppresses shimmer animation
- [ ] Light theme renders correctly after token migration
- [ ] No JS regressions — existing manual flow unchanged
