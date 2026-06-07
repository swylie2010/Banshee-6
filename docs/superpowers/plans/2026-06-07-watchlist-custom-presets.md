# Watchlist Custom Presets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add persistent custom watchlist presets to Banshee 5 — users create named asset groups from the sidebar, manage them via a two-column modal, and presets persist in localStorage across sessions.

**Architecture:** Pure frontend change. `customPresets` state in `App` reads/writes `localStorage`. A derived `watchlists` value merges custom presets with the built-in defaults and replaces all `window.WATCHLISTS` references via props. `PresetsModal` (new component in `parts.jsx`) handles all CRUD and reorder operations.

**Tech Stack:** React (Babel standalone), localStorage. No backend changes, no changes to `data.js` or `api.js`.

---

### Task 1: App data helpers + state + prop threading

**Files:**
- Modify: `ui/app.jsx` — above `App()`, inside `App()`, Sidebar + AssetGrid JSX call sites

- [ ] **Step 1: Add helper functions above `App()`**

Find `function App()` (around line 4008). Insert these two helpers directly above it:

```javascript
/* ── Watchlist custom presets helpers ─────────────────────── */
function loadCustomPresets() {
  try {
    const raw = localStorage.getItem('banshee_custom_presets');
    return raw ? JSON.parse(raw) : [];
  } catch { return []; }
}
function persistCustomPresets(presets) {
  try { localStorage.setItem('banshee_custom_presets', JSON.stringify(presets)); }
  catch {}
}
```

- [ ] **Step 2: Add state to `App()`**

Inside `function App()`, find the existing state declarations block (around line 4010, where `watchlist` state is). Add after the `watchlist`/`setWatchlist` line:

```javascript
const [customPresets, setCustomPresets] = React.useState(() => loadCustomPresets());
const [presetsOpen, setPresetsOpen]     = React.useState(false);
```

- [ ] **Step 3: Add derived `watchlists` + `saveCustomPresets`**

Immediately after the state declarations, add:

```javascript
const watchlists = React.useMemo(
  () => [...customPresets, ...window.WATCHLISTS],
  [customPresets]
);

function saveCustomPresets(presets) {
  setCustomPresets(presets);
  persistCustomPresets(presets);
}
```

- [ ] **Step 4: Add fallback `useEffect`**

After `saveCustomPresets`, add:

```javascript
React.useEffect(() => {
  const allIds = new Set([
    ...customPresets.map(p => p.id),
    ...window.WATCHLISTS.map(w => w.id),
  ]);
  if (!allIds.has(watchlist)) setWatchlist('all');
}, [customPresets]);
```

- [ ] **Step 5: Update keyboard nav**

Find the keyboard nav `useEffect` (around line 4034). Replace:
```javascript
// Before:
const wl = window.WATCHLISTS.find(w => w.id === watchlist);
// After:
const wl = watchlists.find(w => w.id === watchlist);
```

Add `watchlists` to that useEffect's dependency array. It currently ends with `}, [page, openSym, watchlist]);` — change to:
```javascript
}, [page, openSym, watchlist, watchlists]);
```

- [ ] **Step 6: Pass new props to `<Sidebar>`**

Find the `<Sidebar` JSX (around line 4133). Add `watchlists` and `onPresetsOpen` props:

```jsx
<Sidebar
  open={sidebarOpen}
  watchlists={watchlists}
  watchlist={watchlist} setWatchlist={setWatchlist}
  focusedSym={focusedSym}
  radarData={radarData}
  setFocusedSym={openAsset}
  onSearch={handleSymbolSearch}
  onSettings={() => setPage('settings')}
  onMacro={() => setPage('macro')}
  onNews={() => setPage('news')}
  onLab={() => setPage('lab')}
  onRisk={() => setPage('risk')}
  onJournal={() => setPage('journal')}
  onManual={() => setPage('manual')}
  currentPage={page}
  onPresetsOpen={() => setPresetsOpen(true)}
/>
```

- [ ] **Step 7: Pass `watchlists` to `<AssetGrid>`**

Find the `<AssetGrid` JSX (around line 4149). Add:

```jsx
<AssetGrid
  watchlists={watchlists}
  watchlist={watchlist}
  focusedSym={focusedSym}
  onOpen={openAsset}
  radarData={radarData}
  radarLoading={radarLoading}
/>
```

- [ ] **Step 8: Add `PresetsModal` to App render**

Find the closing section of the App return (after all page-conditional renders, before the final `</div>`). Add:

```jsx
{presetsOpen && (
  <window.PresetsModal
    customPresets={customPresets}
    saveCustomPresets={saveCustomPresets}
    watchlist={watchlist}
    setWatchlist={setWatchlist}
    onClose={() => setPresetsOpen(false)}
  />
)}
```

- [ ] **Step 9: Verify in browser**

Start Banshee (`launch_banshee.bat`), open `http://localhost:8765/ui/`, open browser DevTools console. Verify:
- No JavaScript errors
- App loads normally, all 6 default watchlists still appear
- `localStorage.getItem('banshee_custom_presets')` returns `null` (correct — nothing saved yet)

- [ ] **Step 10: Commit**

```bash
cd ~/AntiEverything/Banshee_5
git add ui/app.jsx
git commit -m "feat: customPresets state + watchlists derived + prop threading"
```

---

### Task 2: Sidebar + AssetGrid prop updates

**Files:**
- Modify: `ui/app.jsx` — `Sidebar` function signature + body, `AssetGrid` function signature + body

- [ ] **Step 1: Update `Sidebar` function signature**

Find:
```javascript
function Sidebar({ open, watchlist, setWatchlist, focusedSym, setFocusedSym, radarData, onSearch, onSettings, onMacro, onNews, onLab, onRisk, onJournal, onManual, currentPage }) {
```
Replace with:
```javascript
function Sidebar({ open, watchlists, watchlist, setWatchlist, focusedSym, setFocusedSym, radarData, onSearch, onSettings, onMacro, onNews, onLab, onRisk, onJournal, onManual, currentPage, onPresetsOpen }) {
```

- [ ] **Step 2: Replace `window.WATCHLISTS` references inside `Sidebar`**

Two replacements:

```javascript
// ~line 250 — find the base asset lookup:
// Before: const wl = window.WATCHLISTS.find(w => w.id === watchlist);
// After:
const wl = watchlists.find(w => w.id === watchlist);

// ~line 311 — find the selector map:
// Before: {window.WATCHLISTS.map(w => {
// After:
{watchlists.map(w => {
```

- [ ] **Step 3: Add `CUSTOM PRESETS` button in Sidebar**

Find the WATCHLIST section header in the Sidebar JSX — it looks like:
```jsx
<window.Label>WATCHLIST</window.Label>
<div style={{ display: "flex", flexDirection: "column", gap: 2, marginTop: 8 }}>
  {watchlists.map(w => {
```

Insert a button between the label and the selector `<div>`:

```jsx
<window.Label>WATCHLIST</window.Label>
<button
  onClick={onPresetsOpen}
  style={{
    marginTop: 6,
    marginBottom: 2,
    width: "100%",
    padding: "5px 0",
    background: "transparent",
    border: "1px solid var(--amber)",
    borderRadius: 3,
    color: "var(--amber)",
    fontSize: 10,
    fontFamily: "var(--mono)",
    letterSpacing: "0.14em",
    cursor: "pointer",
  }}
>
  CUSTOM PRESETS
</button>
<div style={{ display: "flex", flexDirection: "column", gap: 2, marginTop: 8, maxHeight: 240, overflowY: "auto" }}>
  {watchlists.map(w => {
```

- [ ] **Step 4: Update `AssetGrid` function signature**

Find:
```javascript
function AssetGrid({ watchlist, focusedSym, onOpen, radarData, radarLoading }) {
```
Replace with:
```javascript
function AssetGrid({ watchlists, watchlist, focusedSym, onOpen, radarData, radarLoading }) {
```

- [ ] **Step 5: Replace `window.WATCHLISTS` inside `AssetGrid`**

```javascript
// Before: const wl = window.WATCHLISTS.find(w => w.id === watchlist);
// After:
const wl = watchlists.find(w => w.id === watchlist);
```

- [ ] **Step 6: Verify in browser**

Hard-refresh (`Ctrl+Shift+R`). Verify:
- `CUSTOM PRESETS` button appears below the WATCHLIST label in the sidebar
- All 6 default watchlists still appear and are selectable
- Switching watchlists populates the grid correctly
- Clicking `CUSTOM PRESETS` has no visible effect yet (modal component not yet defined — no error expected since the `{presetsOpen && ...}` guard prevents rendering)
- No console errors

- [ ] **Step 7: Commit**

```bash
git add ui/app.jsx
git commit -m "feat: sidebar CUSTOM PRESETS button + scrollable selector + watchlists prop"
```

---

### Task 3: PresetsModal component

**Files:**
- Modify: `ui/parts.jsx` — add `PresetsModal` at the end of the file

- [ ] **Step 1: Append PresetsModal to `parts.jsx`**

Open `ui/parts.jsx`, scroll to the very end. Add the full component:

```jsx
/* ── PresetsModal — manage custom watchlist presets ──────── */
window.PresetsModal = function PresetsModal({ customPresets, saveCustomPresets, watchlist, setWatchlist, onClose }) {
  const [selectedId, setSelectedId] = React.useState(customPresets[0]?.id ?? null);
  const [nameVal,    setNameVal]    = React.useState(customPresets[0]?.name ?? '');
  const [addVal,     setAddVal]     = React.useState('');
  const nameTimer = React.useRef(null);

  const selected = customPresets.find(p => p.id === selectedId) ?? null;

  /* sync name input when selection changes */
  React.useEffect(() => {
    setNameVal(selected?.name ?? '');
    setAddVal('');
  }, [selectedId]);

  /* close on Escape */
  React.useEffect(() => {
    const fn = e => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', fn);
    return () => window.removeEventListener('keydown', fn);
  }, []);

  function selectPreset(id) {
    setSelectedId(id);
    setWatchlist(id);
  }

  function handleNewPreset() {
    const p = { id: 'custom_' + Date.now(), name: '', syms: [] };
    saveCustomPresets([p, ...customPresets]);
    setSelectedId(p.id);
  }

  function handleNameChange(val) {
    setNameVal(val);
    clearTimeout(nameTimer.current);
    nameTimer.current = setTimeout(() => {
      saveCustomPresets(customPresets.map(p => p.id === selectedId ? { ...p, name: val } : p));
    }, 400);
  }

  function handleAddTicker() {
    const sym = addVal.trim().toUpperCase();
    if (!sym || !selected || selected.syms.includes(sym)) { setAddVal(''); return; }
    saveCustomPresets(customPresets.map(p =>
      p.id === selectedId ? { ...p, syms: [...p.syms, sym] } : p
    ));
    setAddVal('');
  }

  function handleRemoveTicker(sym) {
    saveCustomPresets(customPresets.map(p =>
      p.id === selectedId ? { ...p, syms: p.syms.filter(s => s !== sym) } : p
    ));
  }

  function handleMoveUp(id) {
    const i = customPresets.findIndex(p => p.id === id);
    if (i <= 0) return;
    const next = [...customPresets];
    [next[i - 1], next[i]] = [next[i], next[i - 1]];
    saveCustomPresets(next);
  }

  function handleMoveDown(id) {
    const i = customPresets.findIndex(p => p.id === id);
    if (i < 0 || i >= customPresets.length - 1) return;
    const next = [...customPresets];
    [next[i], next[i + 1]] = [next[i + 1], next[i]];
    saveCustomPresets(next);
  }

  function handleDelete(id) {
    const remaining = customPresets.filter(p => p.id !== id);
    saveCustomPresets(remaining);
    if (selectedId === id) setSelectedId(remaining[0]?.id ?? null);
  }

  const S = {
    backdrop: {
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.72)',
      zIndex: 200, display: 'flex', alignItems: 'center', justifyContent: 'center',
    },
    panel: {
      background: 'var(--bg-2)', border: '1px solid var(--line)', borderRadius: 6,
      width: 620, maxHeight: '80vh', display: 'flex', flexDirection: 'column',
      overflow: 'hidden',
    },
    header: {
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '12px 16px', borderBottom: '1px solid var(--line)',
    },
    headerLabel: {
      fontFamily: 'var(--mono)', fontSize: 11, letterSpacing: '0.18em',
      color: 'var(--amber)', fontWeight: 600,
    },
    closeBtn: {
      background: 'none', border: 'none', color: 'var(--ink-3)', fontSize: 18,
      cursor: 'pointer', padding: '2px 6px', lineHeight: 1,
    },
    body: { display: 'flex', flex: 1, minHeight: 0 },
    leftCol: {
      width: 220, borderRight: '1px solid var(--line)', display: 'flex',
      flexDirection: 'column', padding: '10px 0',
    },
    newBtn: {
      margin: '0 10px 8px 10px', padding: '5px 0', background: 'transparent',
      border: '1px solid var(--amber)', borderRadius: 3, color: 'var(--amber)',
      fontSize: 10, fontFamily: 'var(--mono)', letterSpacing: '0.14em', cursor: 'pointer',
    },
    presetList: { flex: 1, overflowY: 'auto' },
    presetRow: (isActive) => ({
      display: 'flex', alignItems: 'center', gap: 4, padding: '5px 10px', cursor: 'pointer',
      borderLeft: isActive ? '2px solid var(--amber)' : '2px solid transparent',
      background: isActive ? 'rgba(255,160,0,0.07)' : 'transparent',
    }),
    presetName: (isActive) => ({
      flex: 1, fontFamily: 'var(--mono)', fontSize: 11,
      color: isActive ? 'var(--amber)' : 'var(--ink)', letterSpacing: '0.1em',
      whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
    }),
    iconBtn: {
      background: 'none', border: 'none', color: 'var(--ink-3)', fontSize: 11,
      cursor: 'pointer', padding: '1px 3px', lineHeight: 1,
    },
    dividerRow: {
      display: 'flex', alignItems: 'center', gap: 6, margin: '8px 10px 4px 10px',
    },
    dividerLine: { flex: 1, borderTop: '1px solid var(--line)' },
    dividerLabel: {
      fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--ink-4)', letterSpacing: '0.16em',
    },
    builtinRow: {
      padding: '4px 12px', fontFamily: 'var(--mono)', fontSize: 11,
      color: 'var(--ink-3)', letterSpacing: '0.1em',
    },
    rightCol: { flex: 1, display: 'flex', flexDirection: 'column', padding: 16, gap: 12 },
    placeholder: {
      flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink-4)', letterSpacing: '0.12em',
      textAlign: 'center',
    },
    nameInput: {
      background: 'var(--bg-3)', border: '1px solid var(--line)', borderRadius: 3,
      color: 'var(--ink)', fontFamily: 'var(--mono)', fontSize: 12, padding: '6px 10px',
      letterSpacing: '0.12em', outline: 'none', width: '100%', boxSizing: 'border-box',
    },
    chipsWrap: { display: 'flex', flexWrap: 'wrap', gap: 6, minHeight: 34 },
    chip: {
      display: 'flex', alignItems: 'center', gap: 4, padding: '3px 8px',
      background: 'var(--bg-3)', border: '1px solid var(--line)', borderRadius: 12,
      fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink)', letterSpacing: '0.1em',
    },
    chipX: {
      background: 'none', border: 'none', color: 'var(--ink-3)', fontSize: 13,
      cursor: 'pointer', padding: 0, lineHeight: 1,
    },
    emptyChips: {
      fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--ink-4)', letterSpacing: '0.1em',
      alignSelf: 'center',
    },
    addRow: { display: 'flex', gap: 8 },
    addInput: {
      flex: 1, background: 'var(--bg-3)', border: '1px solid var(--line)', borderRadius: 3,
      color: 'var(--ink)', fontFamily: 'var(--mono)', fontSize: 11, padding: '5px 10px',
      letterSpacing: '0.12em', outline: 'none',
    },
    addBtn: {
      padding: '5px 12px', background: 'transparent', border: '1px solid var(--ink-3)',
      borderRadius: 3, color: 'var(--ink)', fontFamily: 'var(--mono)', fontSize: 10,
      letterSpacing: '0.14em', cursor: 'pointer',
    },
  };

  return (
    <div style={S.backdrop} onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div style={S.panel}>

        {/* Header */}
        <div style={S.header}>
          <span style={S.headerLabel}>MANAGE PRESETS</span>
          <button style={S.closeBtn} onClick={onClose}>×</button>
        </div>

        {/* Body */}
        <div style={S.body}>

          {/* Left column — preset list */}
          <div style={S.leftCol}>
            <button style={S.newBtn} onClick={handleNewPreset}>+ NEW PRESET</button>
            <div style={S.presetList}>
              {customPresets.map((p, i) => (
                <div key={p.id} style={S.presetRow(selectedId === p.id)}
                  onClick={() => selectPreset(p.id)}>
                  <span style={S.presetName(selectedId === p.id)}>
                    {p.name || 'Untitled Preset'}
                  </span>
                  <button style={S.iconBtn} title="Move up"
                    onClick={e => { e.stopPropagation(); handleMoveUp(p.id); }}
                    disabled={i === 0}>▲</button>
                  <button style={S.iconBtn} title="Move down"
                    onClick={e => { e.stopPropagation(); handleMoveDown(p.id); }}
                    disabled={i === customPresets.length - 1}>▼</button>
                  <button style={S.iconBtn} title="Delete preset"
                    onClick={e => { e.stopPropagation(); handleDelete(p.id); }}>🗑</button>
                </div>
              ))}

              {/* Defaults divider */}
              <div style={S.dividerRow}>
                <div style={S.dividerLine} />
                <span style={S.dividerLabel}>DEFAULTS</span>
                <div style={S.dividerLine} />
              </div>

              {/* Built-ins — read only */}
              {window.WATCHLISTS.map(w => (
                <div key={w.id} style={S.builtinRow}>{w.name}</div>
              ))}
            </div>
          </div>

          {/* Right column — editor */}
          <div style={S.rightCol}>
            {!selected ? (
              <div style={S.placeholder}>
                {customPresets.length === 0
                  ? 'Click + NEW PRESET to get started'
                  : 'Select a preset to edit'}
              </div>
            ) : (
              <>
                <input
                  style={S.nameInput}
                  placeholder="Preset name…"
                  value={nameVal}
                  onChange={e => handleNameChange(e.target.value)}
                />
                <div style={S.chipsWrap}>
                  {selected.syms.length === 0
                    ? <span style={S.emptyChips}>No assets yet — add a ticker below</span>
                    : selected.syms.map(sym => (
                        <div key={sym} style={S.chip}>
                          <span>{sym}</span>
                          <button style={S.chipX} onClick={() => handleRemoveTicker(sym)}>×</button>
                        </div>
                      ))
                  }
                </div>
                <div style={S.addRow}>
                  <input
                    style={S.addInput}
                    placeholder="Add ticker (e.g. AAPL, BTC)…"
                    value={addVal}
                    onChange={e => setAddVal(e.target.value)}
                    onKeyDown={e => { if (e.key === 'Enter') handleAddTicker(); }}
                  />
                  <button style={S.addBtn} onClick={handleAddTicker}>ADD</button>
                </div>
              </>
            )}
          </div>

        </div>
      </div>
    </div>
  );
};
```

- [ ] **Step 2: Verify modal opens**

Hard-refresh (`Ctrl+Shift+R`). Click `CUSTOM PRESETS` in the sidebar. Verify:
- Dark backdrop + centered panel appears
- Header shows `MANAGE PRESETS` in amber + `×` close button
- Left column: `+ NEW PRESET` button, `── DEFAULTS ──` divider, 6 built-in names below it
- Right column: "Click + NEW PRESET to get started" placeholder
- Clicking outside the panel (on backdrop) closes it
- Pressing Escape closes it

- [ ] **Step 3: Test create + name + add tickers**

With modal open:
1. Click `+ NEW PRESET` — verify a row "Untitled Preset" appears in left column, right column shows name input + empty chips + add input
2. Type `My Crypto` in the name input — wait 500ms — verify left column row updates to "My Crypto"
3. Type `BTC` in the add input, press Enter — verify BTC chip appears
4. Type `ETH`, click ADD — verify ETH chip appears
5. Click `×` on BTC chip — verify BTC disappears, ETH remains

- [ ] **Step 4: Test persistence across refresh**

1. Close the modal
2. Verify "My Crypto" appears in the sidebar watchlist selector
3. Click it — verify AssetGrid updates (will show ETH with live data, any other tickers as loading/mock)
4. Hard-refresh (`Ctrl+Shift+R`)
5. Verify "My Crypto" still appears in sidebar
6. Open modal — verify preset and ETH ticker are intact
7. Confirm in console: `JSON.parse(localStorage.getItem('banshee_custom_presets'))` shows the preset

- [ ] **Step 5: Test reorder + delete with active fallback**

1. Create a second preset "My Tech" with NVDA
2. Open modal — verify both presets appear in order: My Crypto, My Tech
3. Click ▲ on "My Tech" — verify it moves above "My Crypto"
4. Select "My Crypto" as the active watchlist (click it in the modal left column)
5. Click 🗑 on "My Crypto" — verify it disappears; "My Tech" becomes selected in the modal
6. Close modal — verify sidebar shows "My Tech" selected (or "ALL SIGNALS" if My Tech was also selected and deleted)
7. Repeat delete to remove "My Tech" while it is the active watchlist — verify sidebar falls back to ALL SIGNALS

- [ ] **Step 6: Commit**

```bash
git add ui/parts.jsx
git commit -m "feat: PresetsModal — create/name/ticker chips/reorder/delete custom presets"
```

---

### Task 4: Mark complete + ACTIVE_TASK.md update

**Files:**
- Modify: `ACTIVE_TASK.md`

- [ ] **Step 1: Mark watchlist custom groups done**

In `ACTIVE_TASK.md`, find:
```
- [ ] **Watchlist custom groups** — spec not yet written. V4 let users create named groups of assets...
```
Replace with:
```
- [x] **Watchlist custom groups** — DONE (2026-06-07). `PresetsModal` (parts.jsx): two-column overlay, create/rename/add tickers/reorder/delete. `customPresets` localStorage state in App; `watchlists` derived prop replaces all `window.WATCHLISTS` references. Spec + plan at docs/superpowers/.
```

- [ ] **Step 2: Commit**

```bash
git add ACTIVE_TASK.md
git commit -m "docs: mark watchlist custom groups complete"
```
