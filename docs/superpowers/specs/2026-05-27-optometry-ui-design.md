# Optometry UI — SMC Lens System

**Date:** 2026-05-27  
**Feature:** Phase 7 #5 — SMC display refinement (visual layer)  
**Scope:** Frontend only — `app.jsx` + `parts.jsx`. No backend changes.

---

## Problem

The SMC overlay presents all information simultaneously. The result is a "haystack" — rich data that requires too much active decoding to extract a trading decision. The one clear prior win (OTE axis labels) proved that instant readability beats completeness. This feature extends that principle across the full overlay.

---

## Solution: Four Named Lenses

Four progressive views of the same SMC data, each answering one question:

| # | Key | Name | Question answered |
|---|---|---|---|
| 1 | `1` | ALL | Full spaghetti — see everything |
| 2 | `2` | BATTLEFIELD | Should I be long or short? |
| 3 | `3` | FOOTPRINTS | Where did institutions leave a mess? |
| 4 | `4` | SNIPER | What's the highest-conviction trigger right now? |

The ALL lens (L1) is the current state — nothing removed, nothing changed. Lenses 2–4 progressively narrow focus to what matters for that question.

---

## Layer Visibility Table

| SMC Layer | L1 ALL | L2 BATTLEFIELD | L3 FOOTPRINTS | L4 SNIPER |
|---|---|---|---|---|
| PD background (premium/discount gradients) | ✓ | ✓ | — | — |
| OTE price lines (62% / 79%) | ✓ | ✓ | — | ✓ |
| HTF key levels (dotted amber) | ✓ | ✓ | — | — |
| Swing markers (HH/HL/LH/LL + BOS/CHoCH) | ✓ | ✓ | — | — |
| FVGs | ✓ | — | ✓ full | — |
| OBs — inducement-swept (green border) | ✓ | — | — | ✓ full |
| OBs — inducement-pending (amber border) | ✓ | — | ✓ full | ✓ 40% opacity |
| OBs — candidate (dashed, gate_passed=false) | ✓ | — | ✓ full | — |
| OBs — active, no inducement | ✓ | — | — | ✓ 40% opacity |
| OBs — touched / degraded | ✓ | — | — | ✓ 20% opacity |
| EQL/EQH liquidity pools | ✓ | — | ✓ | — |

**Rationale for non-obvious calls:**
- OTE visible in L4 SNIPER: the golden pocket is the target entry depth — a sniper needs it
- Swing markers in L2 BATTLEFIELD: HH/HL sequence and last BOS directly answer "am I in a bullish or bearish structure?"
- Inducement-pending OBs at 40% in L4: not the trigger yet, but a sniper should know they exist nearby
- EQL in L3 FOOTPRINTS: liquidity pools ARE the institutional footprint — they belong alongside FVGs

---

## State

`lensMode: number` (1–4, default 1) owned by `AnalysisPage`.

- Resets to 1 when `asset` changes (new asset = fresh full view)
- Persists across SMC/GH/Nexus tab switches within the same asset session
- Does not persist across page navigations (AnalysisPage unmount)

---

## UI

### Lens buttons on TF bar

The existing TF bar (`tab !== "nexus"`) gets lens buttons appended — visible only when `tab === "smc"`.

```
[ TF ]  [ 1H ][ 4H ][ 1D ]          [ ALL ][ BATTLEFIELD ][ FOOTPRINTS ][ SNIPER ]
```

- Same monospace 10px style as TF buttons
- Active lens: cyan accent fill (`var(--cyan)`) with dark text, matching TF active style
- Inactive: transparent background, `var(--ink-2)` text
- Separated from TF group by a gap (not connected)
- The outer TF bar container changes from `display: "inline-flex"` to full-width `display: "flex"` with `justifyContent: "space-between"` to accommodate both groups

### Keyboard shortcuts

`keydown` listener registered in `AnalysisPage` via `useEffect`, active only when `tab === "smc"`.

| Key | Action |
|---|---|
| `1` | Switch to L1 ALL |
| `2` | Switch to L2 BATTLEFIELD |
| `3` | Switch to L3 FOOTPRINTS |
| `4` | Switch to L4 SNIPER |

Listener is cleaned up on unmount and when tab changes away from `"smc"`.

---

## Rendering

`lensMode` passed as a prop to `Chart`. Added to the SMC `useEffect` dependency array alongside `smcData` and `showSMC` — lens switching triggers the existing teardown/reattach cycle automatically.

### Filtering logic (applied before attach)

In the SMC `useEffect`:

**PD background:** Skip `attachPrimitive(pdPrim)` for L3, L4.

**OTE lines:** Skip `createPriceLine` for OTE in L2 BATTLEFIELD and L3 FOOTPRINTS. Show in L1 ALL and L4 SNIPER.

**HTF key levels:** Skip for L3, L4.

**Swing markers:** Skip `attachPrimitive(mkPrim)` for L3, L4.

**FVGs (via `smcToZones`):** L2 BATTLEFIELD and L4 SNIPER filter out all FVG-type zones before passing to `SMCZonePrimitive`. L3 FOOTPRINTS passes FVGs through at full opacity.

**OBs (via `smcToZones`):** OB-type zones only — FVG zones are handled separately above. Per-OB filtering:
- L2 BATTLEFIELD: exclude all OBs
- L3 FOOTPRINTS: include only OBs where `has_pending_inducement=true` or `gate_passed=false` (candidates); exclude active/touched/degraded OBs with no inducement
- L4 SNIPER:
  - `inducement_swept=true` → include at full opacity
  - `has_pending_inducement=true` OR (`status="active"` AND no inducement) → include at 40% opacity
  - `status="touched"` or `status="degraded"` → include at 20% opacity
  - `gate_passed=false` (candidates) → exclude

**EQL lines:** Skip `createPriceLine` for EQL pools in L2 BATTLEFIELD and L4 SNIPER.

---

## Files Changed

| File | Change |
|---|---|
| `ui/app.jsx` | Add `lensMode` state to `AnalysisPage`; pass to `Chart`; add lens buttons to TF bar; add keydown listener |
| `ui/parts.jsx` | Add `lensMode` prop to `Chart`; add filtering logic in SMC `useEffect` |

No other files touched.

---

## Out of Scope (deferred)

**Hover composite (L4):** In L4 SNIPER, hovering an OB briefly reveals the nearest FVG or OTE line. Requires mouse-position tracking against chart canvas and temporary primitive state. Backlog item — implement after lenses are validated.
