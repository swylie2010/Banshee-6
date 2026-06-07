# Watchlist Custom Presets — Design Spec
**Date:** 2026-06-07
**Status:** Approved — ready for implementation plan

---

## Overview

Users can create, name, and populate their own watchlist presets from the sidebar. Custom presets stack above the 6 built-in defaults in the watchlist selector, can be reordered up/down, and persist across sessions via `localStorage`. The management UI is a two-column floating modal triggered by a `CUSTOM PRESETS` button in the sidebar.

---

## Data & Persistence

**Storage:** `localStorage` key `banshee_custom_presets`
**Schema:** `Array<{ id: string, name: string, syms: string[] }>`
- `id` generated as `"custom_" + Date.now()` at creation time
- `syms` is an array of uppercase ticker strings (no validation against master list — any symbol accepted)

**Runtime merge:**
- `App` reads `banshee_custom_presets` from localStorage on mount, merges with built-in defaults into a `watchlists` state:
  ```
  watchlists = [...customPresets, ...BUILT_IN_WATCHLISTS]
  ```
- `BUILT_IN_WATCHLISTS` is the existing `window.WATCHLISTS` array (unchanged in `data.js`)
- `watchlists` is passed as a prop to `Sidebar` and `AssetGrid`; all `window.WATCHLISTS` references in those components are replaced with the prop
- `App`'s keyboard nav (`ArrowUp`/`ArrowDown`) also reads from `watchlists` state instead of `window.WATCHLISTS`

**Save behavior:** Changes write to localStorage immediately on every discrete action (ticker add, ticker remove, preset delete, reorder). Name field debounces 400ms before saving.

**Active watchlist fallback:** If the user deletes the currently selected preset, `watchlist` state falls back to `"all"`.

---

## Components

### `PresetsModal` (new — `parts.jsx`)

Floating overlay with a dark semi-transparent backdrop (`rgba(0,0,0,0.72)`). Centered panel, ~620px wide, max 80vh tall with internal scrolling.

**Header row:** `MANAGE PRESETS` label (amber, monospace) + `×` close button (top-right).

**Two-column body:**

**Left column (~220px) — preset list**
- `+ NEW PRESET` button at top (outlined amber)
- Custom preset rows: name label + `▲` `▼` arrows + `🗑` trash icon. Active/selected row highlighted with amber left border
- `── DEFAULTS ──` divider (greyed label)
- Built-in rows: name label only, no controls, `var(--ink-3)` text
- The entire left column scrolls independently if needed

**Right column (flex remainder) — editor**
- Shown when a custom preset is selected; shows a placeholder message when a built-in is selected ("Built-in presets cannot be edited")
- **Name input:** text input at top, auto-saves on change (debounced 400ms)
- **Ticker chips:** each added symbol shown as a pill with `×` to remove. Chips wrap.
- **Add input:** search-style text input at bottom with `ADD` button (or Enter key). Accepts any ticker string; uppercases on add. Duplicate tickers silently ignored.
- Empty name defaults display as `"Untitled Preset"` in the list but the input remains blank

**Footer:** `CLOSE` button (or press Escape)

### `Sidebar` changes

- `CUSTOM PRESETS` button placed directly below the `WATCHLIST` section label — outlined, amber, small (same weight as existing `+ ADD` style buttons in the app)
- Watchlist selector list gets `overflowY: auto` + `maxHeight: 240px` so it scrolls when many presets are present
- Replace `window.WATCHLISTS` with `watchlists` prop throughout

### `AssetGrid` changes

- Replace `window.WATCHLISTS.find(...)` with `watchlists.find(...)` using the `watchlists` prop

### `App` changes

- `customPresets` state — array of user-created presets only, initialized from `loadCustomPresets()` (reads localStorage)
- `watchlists` derived value — `[...customPresets, ...BUILT_IN_WATCHLISTS]`, recomputed whenever `customPresets` changes
- `presetsOpen` boolean state — controls `PresetsModal` visibility
- Helper `saveCustomPresets(presets)` — sets `customPresets` state + writes to localStorage
- Keyboard nav updated to use `watchlists` state

---

## Interactions

| Action | Behavior |
|---|---|
| Click `CUSTOM PRESETS` | Opens `PresetsModal` |
| Click `+ NEW PRESET` | Adds blank preset to top of custom list, selects it, focuses name input |
| Type preset name | Debounced 400ms → saves to localStorage |
| Type ticker + Enter/Add | Uppercases, appends to `syms`, saves immediately; duplicate → no-op |
| Click `×` on ticker chip | Removes sym, saves immediately |
| Click `▲` / `▼` on preset row | Swaps position with adjacent custom preset, saves immediately |
| Click `🗑` on preset row | Removes preset, selects next custom preset (or built-in "all" if none remain); saves immediately |
| Click a preset row | Selects it in the sidebar watchlist AND opens it for editing in right column |
| Click `×` / `CLOSE` / Escape | Closes modal |
| Delete active preset | `watchlist` state falls back to `"all"` |

**Reorder scope:** `▲`/`▼` only moves custom presets relative to each other. Built-in defaults are always anchored below the divider in both the modal and the sidebar selector.

**New preset defaults:** `id = "custom_" + Date.now()`, `name = ""`, `syms = []`. Appears in sidebar immediately with display name "Untitled Preset" until renamed.

**Sidebar selector:** Custom presets appear above built-ins, in the user's chosen order. Both sections share the same selector style; custom presets have no extra affordance in the selector itself (management is exclusively in the modal).

---

## Edge Cases

- **No custom presets:** Left column shows only the defaults below the divider; `+ NEW PRESET` is the only interactive element above it
- **Many presets:** Left column scrolls independently; sidebar selector scrolls via `maxHeight: 240px`
- **Preset with no tickers:** Valid to save (user may be mid-edit). `AssetGrid` renders empty grid with "0 assets" label — same behavior as selecting a watchlist with no matching radar data
- **Symbol not in `ASSETS` array:** Accepted and stored. `AssetGrid` will attempt radar fetch via `fetchRadar`; if Core has no data it renders with mock/loading state — same as sidebar search custom symbols today
- **localStorage unavailable:** Wrapped in try/catch; graceful fallback to built-ins only, `CUSTOM PRESETS` button still shows but modal opens read-only with an error note

---

## Files Touched

| File | Change |
|---|---|
| `ui/app.jsx` | `watchlists` state, `presetsOpen` state, `saveCustomPresets()`, pass props to Sidebar/AssetGrid, update keyboard nav |
| `ui/parts.jsx` | New `PresetsModal` component |
| `ui/app.jsx` Sidebar fn | `CUSTOM PRESETS` button, `watchlists` prop, scrollable selector |
| `ui/app.jsx` AssetGrid fn | `watchlists` prop |

No backend changes. No changes to `data.js` or `api.js`.

---

## Out of Scope

- Drag-and-drop reordering (▲/▼ is sufficient for V1)
- Renaming built-in defaults
- Sharing/exporting preset lists
- Backend sync (localStorage is appropriate for a single-user local tool)
