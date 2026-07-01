/* SettingsPage — extracted from app.jsx */
const { useState, useEffect } = React;

/* ── SettingsPage ──────────────────────────────────────────── */
const AI_PROVIDERS = ["Gemini", "OpenAI", "Anthropic", "Ollama", "Custom"];

const MCP_CONFIG_SNIPPET = `{
  "mcpServers": {
    "banshee-pro": {
      "command": "python",
      "args": ["C:/Users/swyli/AntiEverything/Banshee_6/mcp_server.py"]
    }
  }
}`;

const MCP_TOOLS = [
  ["get_regime",            "lightweight regime bucket + go/no-go (fast, cached)"],
  ["get_macro_weather",     "global macro environment — VIX, yield curve, liquidity"],
  ["get_watchlist",         "user's saved symbol list — call before scan_assets"],
  ["get_asset_radar",       "full multi-timeframe technical analysis for one asset"],
  ["get_smc_structure",     "SMC structure map — swings, BOS/CHoCH, FVGs, order blocks"],
  ["scan_assets",           "ranked scan across a list of symbols"],
  ["synthesize_nexus",      "top-down macro + micro + news AI briefing"],
  ["build_execution_plan",  "position sizing and R-target execution plan"],
  ["read_market_intel",     "daily Predator briefing or RSS fallback"],
  ["get_strategy_results",  "retrieve saved Strategy Lab backtests"],
  ["open_paper_trade",      "open a new paper trade"],
  ["check_kill_switch",     "close all positions if CRACK DETECTED (domino ≥ 2)"],
  ["log_signal_outcome",    "record exit reason or note on any trade"],
  ["get_signal_log",        "retrieve judged trades + regime/exit-reason stats"],
];

function MCPConnectionBlock() {
  const [copied, setCopied] = useState(false);

  function handleCopy() {
    navigator.clipboard.writeText(MCP_CONFIG_SNIPPET).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
      <div>
        <div style={{ marginBottom: 8, display: "flex", alignItems: "center", gap: 12 }}>
          <window.Label>CLAUDE CONFIG SNIPPET</window.Label>
          <span className="mono" style={{ fontSize: 11, color: "var(--ink-4)", letterSpacing: "0.12em" }}>
            paste into ~/.claude/.mcp.json → mcpServers
          </span>
        </div>
        <pre style={{
          background: "var(--bg-3)", border: "1px solid var(--line-2)",
          padding: "12px 14px", margin: 0,
          fontFamily: "'JetBrains Mono', monospace", fontSize: 12,
          color: "var(--cyan)", letterSpacing: "0.05em", lineHeight: 1.7,
          overflowX: "auto", whiteSpace: "pre",
        }}>
          {MCP_CONFIG_SNIPPET}
        </pre>
        <div style={{ marginTop: 10, display: "flex", alignItems: "center", gap: 14 }}>
          <button onClick={handleCopy} style={{
            padding: "7px 18px",
            background: copied ? "rgba(52,211,153,0.12)" : "rgba(56,189,248,0.1)",
            color: copied ? "var(--buy)" : "var(--cyan)",
            border: `1px solid ${copied ? "var(--buy)" : "var(--cyan)"}`,
            cursor: "pointer",
            fontFamily: "'JetBrains Mono', monospace", fontSize: 13, fontWeight: 700, letterSpacing: "0.18em",
          }}>
            {copied ? "✓ COPIED" : "COPY"}
          </button>
          <span className="mono" style={{ fontSize: 11, color: "var(--ink-4)", letterSpacing: "0.1em" }}>
            Core must be running on :8765 before MCP tools respond
          </span>
        </div>
      </div>
      <div>
        <div style={{ marginBottom: 8 }}><window.Label>AVAILABLE TOOLS</window.Label></div>
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {MCP_TOOLS.map(([name, desc]) => (
            <div key={name} style={{ display: "flex", gap: 10, alignItems: "baseline" }}>
              <span className="mono" style={{ fontSize: 12, color: "var(--cyan)", letterSpacing: "0.06em", flexShrink: 0, minWidth: 190 }}>
                {name}
              </span>
              <span className="mono" style={{ fontSize: 11, color: "var(--ink-3)", letterSpacing: "0.08em", lineHeight: 1.5 }}>
                {desc}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

const INPUT_STYLE = {
  width: "100%", boxSizing: "border-box",
  background: "var(--bg-3)", border: "1px solid var(--line-2)",
  color: "var(--ink)", padding: "7px 10px",
  fontFamily: "'JetBrains Mono', monospace", fontSize: 13,
  letterSpacing: "0.06em", outline: "none",
};

const SELECT_STYLE = {
  ...INPUT_STYLE,
  cursor: "pointer",
  appearance: "none", WebkitAppearance: "none",
  backgroundImage: "url(\"data:image/svg+xml,%3Csvg width='10' height='6' viewBox='0 0 10 6' fill='none' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M1 1L5 5L9 1' stroke='%2394a3b8' stroke-width='1.5'/%3E%3C/svg%3E\")",
  backgroundRepeat: "no-repeat", backgroundPosition: "right 10px center",
  paddingRight: 30,
};

/* ── DATA SOURCES ──────────────────────────────────────────── */

const PROVIDER_META = {
  coinbase:  { label: "COINBASE",  note: "free · no key needed",           hasKey: false },
  alpaca:    { label: "ALPACA",    note: "uses your Alpaca key",            hasKey: false },
  coingecko: { label: "COINGECKO", note: "key optional · Pro unlocks more", hasKey: true },
  yfinance:  { label: "YFINANCE",  note: "options chain · earnings calendar", hasKey: false },
};

const TIER_ICON  = { FAST: "⚡", GOOD: "◈", SLOW: "○", UNTESTED: "◌" };
const TIER_COLOR = {
  FAST:     "var(--buy)",
  GOOD:     "var(--cyan)",
  SLOW:     "var(--ink-3)",
  UNTESTED: "var(--ink-4)",
};

function speedPct(avg_ms) {
  if (!avg_ms) return 5;
  if (avg_ms <= 300)  return Math.max(70, 95 - avg_ms / 20);
  if (avg_ms <= 2000) return Math.max(35, 70 - (avg_ms - 300) / 50);
  return Math.max(5, 35 - (avg_ms - 2000) / 300);
}

function Toggle({ on, onChange }) {
  return (
    <div
      onClick={onChange}
      style={{
        width: 36, height: 18, borderRadius: 9, cursor: "pointer", flexShrink: 0,
        background: on ? "var(--cyan)" : "var(--bg-3)",
        border: `1px solid ${on ? "var(--cyan)" : "var(--line-2)"}`,
        position: "relative", transition: "background 0.2s",
      }}
    >
      <div style={{
        position: "absolute", top: 2, left: on ? 18 : 2,
        width: 12, height: 12, borderRadius: 6,
        background: on ? "var(--bg-0)" : "var(--ink-4)",
        transition: "left 0.2s",
      }} />
    </div>
  );
}

function DataSourceRow({ name, speed, enabled, onToggle, cgKey, onCgKeyChange, cgKeyType, onCgKeyTypeChange, onTest, testStatus }) {
  const meta = PROVIDER_META[name];
  const tier = (enabled && speed?.tier) ? speed.tier : "UNTESTED";
  const avg  = enabled ? speed?.avg_ms : null;
  const pct  = enabled ? speedPct(avg) : 0;

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14 }}>
      <span className="mono" style={{ fontSize: 13, color: TIER_COLOR[tier], width: 16, flexShrink: 0 }}>
        {enabled ? TIER_ICON[tier] : "◌"}
      </span>
      <span className="mono" style={{ fontSize: 12, color: "var(--ink)", letterSpacing: "0.14em", width: 96, flexShrink: 0 }}>
        {meta.label}
      </span>
      <Toggle on={enabled} onChange={onToggle} />
      {enabled && (
        <span className="mono" style={{ fontSize: 11, color: TIER_COLOR[tier], width: 72, flexShrink: 0, letterSpacing: "0.1em" }}>
          {tier}{avg ? ` · ${avg < 1000 ? avg + "ms" : (avg / 1000).toFixed(1) + "s"}` : ""}
        </span>
      )}
      {enabled && (
        <div style={{ width: 100, height: 6, background: "var(--bg-3)", flexShrink: 0 }}>
          <div style={{ width: `${pct}%`, height: "100%", background: TIER_COLOR[tier], transition: "width 0.4s" }} />
        </div>
      )}
      {meta.hasKey && enabled ? (
        <>
          <input
            value={cgKey}
            onChange={e => onCgKeyChange(e.target.value)}
            placeholder="API key (optional)"
            style={{ ...INPUT_STYLE, width: 180, fontSize: 12 }}
          />
          <select
            value={cgKeyType}
            onChange={e => onCgKeyTypeChange(e.target.value)}
            style={{ ...INPUT_STYLE, width: 68, fontSize: 11, padding: "4px 6px", cursor: "pointer" }}
          >
            <option value="demo">demo</option>
            <option value="pro">pro</option>
          </select>
        </>
      ) : !meta.hasKey && !enabled ? (
        <span className="mono" style={{ fontSize: 11, color: "var(--ink-4)", letterSpacing: "0.08em" }}>
          {meta.note}
        </span>
      ) : null}
      {name === "coingecko" && enabled && (
        <button
          onClick={onTest}
          disabled={testStatus === "testing"}
          style={{
            padding: "4px 12px", background: "var(--bg-3)",
            border: "1px solid var(--line-2)", color: "var(--cyan)",
            fontFamily: "'JetBrains Mono', monospace", fontSize: 11,
            letterSpacing: "0.14em", cursor: "pointer", flexShrink: 0,
          }}
        >
          {testStatus === "testing" ? "TESTING…" : testStatus === "ok" ? "✓ OK" : testStatus === "error" ? "✗ ERR" : "TEST"}
        </button>
      )}
    </div>
  );
}

function DataSourcesSection({ cgKey, onCgKeyChange, cgKeyType, onCgKeyTypeChange, onSaveCgKey, saveStatus, onSettingsSave }) {
  const [speed, setSpeed] = React.useState({});
  const [testStatus, setTestStatus] = React.useState(null);
  const [customOpen, setCustomOpen] = React.useState(false);
  const [customName, setCustomName] = React.useState("");
  const [customUrl, setCustomUrl] = React.useState("");
  const [customKey, setCustomKey] = React.useState("");
  const [customClass, setCustomClass] = React.useState("both");
  const [customTestStatus, setCustomTestStatus] = React.useState(null);

  const providerKeys = ["coinbase", "alpaca", "coingecko", "yfinance"];
  const anyEnabled = providerKeys.some(n => !!(speed[n]?.enabled)) || !!(speed["custom"]?.enabled);

  React.useEffect(() => {
    window.API.fetchDataSourceSpeed().then(d => {
      if (d) {
        setSpeed(d);
        // Pre-populate custom fields from speed report if available
        if (d.custom) {
          setCustomName(d.custom.name || "");
          setCustomUrl(d.custom.base_url || "");
          setCustomKey(d.custom.api_key || "");
          setCustomClass(d.custom.asset_class || "both");
        }
      }
    });
  }, []);

  function isEnabled(name) {
    return !!(speed[name]?.enabled);
  }

  async function handleToggle(name) {
    const newEnabled = !isEnabled(name);
    // Optimistic UI update
    setSpeed(prev => ({ ...prev, [name]: { ...prev[name], enabled: newEnabled } }));
    // Persist via settings save — server merges nested keys, so sending just {enabled} is safe
    const keyMap = {
      coinbase: "COINBASE", alpaca: "ALPACA_KEY",
      coingecko: "COINGECKO", yfinance: "YFINANCE",
    };
    const settingsKey = keyMap[name];
    if (settingsKey && onSettingsSave) {
      await onSettingsSave({ [settingsKey]: { enabled: newEnabled } });
    }
    // Refresh speed report
    window.API.fetchDataSourceSpeed().then(d => { if (d) setSpeed(d); });
  }

  async function handleTest() {
    setTestStatus("testing");
    await onSaveCgKey();
    const result = await window.API.testCoinGecko();
    if (result?.speed) setSpeed(result.speed);
    setTestStatus(result?.price ? "ok" : "error");
    setTimeout(() => setTestStatus(null), 3000);
  }

  async function handleCustomTest() {
    setCustomTestStatus("testing");
    if (onSettingsSave) {
      await onSettingsSave({
        CUSTOM_DATA: { enabled: true, name: customName, base_url: customUrl, api_key: customKey, asset_class: customClass }
      });
    }
    const result = await window.API.testCustomSource();
    if (result?.speed) setSpeed(result.speed);
    setCustomTestStatus(result?.price ? "ok" : "error");
    setTimeout(() => setCustomTestStatus(null), 3000);
  }

  return (
    <SettingsSection title="▸ DATA SOURCES">
      {!anyEnabled && (
        <div className="mono" style={{
          marginBottom: 16, padding: "10px 14px",
          background: "var(--bg-3)", border: "1px solid var(--sell)",
          color: "var(--sell)", fontSize: 11, letterSpacing: "0.08em",
        }}>
          No data providers enabled — Banshee has no market data source. Enable at least one below.
        </div>
      )}
      <div style={{ marginBottom: 16, color: "var(--ink-3)", fontSize: 11, fontFamily: "monospace", letterSpacing: "0.08em" }}>
        Banshee tries enabled providers fastest-first. Toggle to activate. Latency populates during use.
      </div>
      {providerKeys.map(name => (
        <DataSourceRow
          key={name}
          name={name}
          speed={speed[name]}
          enabled={isEnabled(name)}
          onToggle={() => handleToggle(name)}
          cgKey={name === "coingecko" ? cgKey : ""}
          onCgKeyChange={onCgKeyChange}
          cgKeyType={cgKeyType}
          onCgKeyTypeChange={onCgKeyTypeChange}
          onTest={handleTest}
          testStatus={name === "coingecko" ? testStatus : null}
        />
      ))}
      {saveStatus && (
        <div className="mono" style={{ fontSize: 11, color: saveStatus.startsWith("✗") ? "var(--sell)" : "var(--buy)", marginTop: 4 }}>
          {saveStatus}
        </div>
      )}

      {/* Custom source */}
      <div
        onClick={() => setCustomOpen(o => !o)}
        style={{ cursor: "pointer", color: "var(--ink-3)", fontSize: 11, fontFamily: "monospace",
                 letterSpacing: "0.14em", marginTop: 18, marginBottom: customOpen ? 10 : 0 }}
      >
        {customOpen ? "▾" : "▸"} ADD CUSTOM SOURCE
      </div>
      {customOpen && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8, marginLeft: 16 }}>
          {[
            { label: "NAME",     value: customName, set: setCustomName, placeholder: "My Data Source" },
            { label: "BASE URL", value: customUrl,  set: setCustomUrl,  placeholder: "https://..." },
            { label: "API KEY",  value: customKey,  set: setCustomKey,  placeholder: "(optional)" },
          ].map(({ label, value, set, placeholder }) => (
            <div key={label} style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <span className="mono" style={{ fontSize: 11, color: "var(--ink-3)", width: 72, letterSpacing: "0.1em" }}>{label}</span>
              <input value={value} onChange={e => set(e.target.value)} placeholder={placeholder}
                     style={{ ...INPUT_STYLE, width: 240, fontSize: 12 }} />
            </div>
          ))}
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <span className="mono" style={{ fontSize: 11, color: "var(--ink-3)", width: 72, letterSpacing: "0.1em" }}>COVERS</span>
            <select value={customClass} onChange={e => setCustomClass(e.target.value)}
                    style={{ ...INPUT_STYLE, width: 100, fontSize: 11, padding: "4px 6px", cursor: "pointer" }}>
              <option value="both">BOTH</option>
              <option value="crypto">CRYPTO</option>
              <option value="equity">EQUITY</option>
            </select>
          </div>
          <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
            <button onClick={handleCustomTest} disabled={!customUrl || customTestStatus === "testing"}
                    style={{ padding: "4px 14px", background: "var(--bg-3)", border: "1px solid var(--line-2)",
                             color: "var(--cyan)", fontFamily: "'JetBrains Mono', monospace",
                             fontSize: 11, letterSpacing: "0.14em", cursor: "pointer" }}>
              {customTestStatus === "testing" ? "TESTING…" : customTestStatus === "ok" ? "✓ OK" : customTestStatus === "error" ? "✗ ERR" : "TEST"}
            </button>
          </div>
          <div className="mono" style={{ fontSize: 10, color: "var(--ink-4)", marginTop: 4, maxWidth: 400 }}>
            Expected shape — spot: GET /spot?symbol=BTC returns {"{"}"price": 123.45{"}"} · ohlcv: GET /ohlcv?symbol=BTC&timeframe=1d&limit=10 returns {"{"}"bars": [{"{"}...{"}"}]{"}"}
          </div>
        </div>
      )}
    </SettingsSection>
  );
}

function SettingsSection({ title, children }) {
  return (
    <div style={{ background: "var(--bg-2)", border: "1px solid var(--line)", padding: "20px 24px" }}>
      <div className="mono" style={{ fontSize: 12, color: "var(--cyan)", letterSpacing: "0.22em", fontWeight: 700, marginBottom: 18 }}>
        {title}
      </div>
      {children}
    </div>
  );
}

function SettingsField({ label, hint, children }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: 6 }}>
        <window.Label>{label}</window.Label>
        {hint && <span className="mono" style={{ fontSize: 11, color: "var(--ink-4)", letterSpacing: "0.12em" }}>{hint}</span>}
      </div>
      {children}
    </div>
  );
}

function SaveRow({ onSave, status }) {
  const color = status === "saved" ? "var(--buy)" : status === "error" ? "var(--sell)" : "var(--ink-3)";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 8 }}>
      <button onClick={onSave} style={{
        padding: "7px 18px", background: "var(--cyan)", color: "var(--bg-0)",
        border: "none", cursor: "pointer",
        fontFamily: "'JetBrains Mono', monospace", fontSize: 13, fontWeight: 700, letterSpacing: "0.18em",
      }}>SAVE</button>
      {status && (
        <span className="mono" style={{ fontSize: 13, color, letterSpacing: "0.14em" }}>
          {status === "saved" ? "✓ SAVED" : status === "saving" ? "SAVING…" : `✗ ${status}`}
        </span>
      )}
    </div>
  );
}

function PinSettings() {
  const [enabled, setEnabled] = React.useState(localStorage.getItem('banshee_pin_enabled') === 'true');
  const [pin,     setPin]     = React.useState(localStorage.getItem('banshee_pin') || '');
  const [newPin,  setNewPin]  = React.useState('');
  const [saved,   setSaved]   = React.useState(false);

  const toggleEnable = () => {
    const next = !enabled;
    setEnabled(next);
    localStorage.setItem('banshee_pin_enabled', String(next));
  };

  const savePin = () => {
    if (newPin.length !== 4 || !/^\d{4}$/.test(newPin)) return;
    localStorage.setItem('banshee_pin', newPin);
    setPin(newPin);
    setNewPin('');
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const inputStyle = {
    background: "var(--bg-3)", border: "1px solid var(--line)", color: "var(--ink)",
    fontFamily: "monospace", fontSize: 13, padding: "6px 10px",
    borderRadius: 3, outline: "none", width: 80, letterSpacing: "0.2em"
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <label style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer" }}>
        <input type="checkbox" checked={enabled} onChange={toggleEnable} />
        <span className="mono" style={{ fontSize: 12, color: "var(--ink-3)", letterSpacing: "0.08em" }}>
          Require PIN on launch
        </span>
      </label>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <input
          type="password"
          maxLength={4}
          value={newPin}
          onChange={e => setNewPin(e.target.value.replace(/\D/g, '').slice(0, 4))}
          placeholder={pin ? '••••' : '4 digits'}
          style={inputStyle}
        />
        <button onClick={savePin} disabled={newPin.length !== 4}
          style={{ fontFamily: "inherit", fontSize: 11, letterSpacing: "0.1em",
            background: saved ? "var(--buy)" : "var(--bg-3)",
            color: saved ? "#000" : "var(--ink)", border: "1px solid var(--line)",
            padding: "6px 14px", borderRadius: 3, cursor: "pointer" }}>
          {saved ? "✓ SAVED" : "SET PIN"}
        </button>
      </div>
      {enabled && !pin && (
        <div className="mono" style={{ fontSize: 11, color: "var(--amber)" }}>
          Set a PIN above to activate the lock
        </div>
      )}
      {pin && (
        <div className="mono" style={{ fontSize: 11, color: "var(--ink-4)" }}>
          PIN is set · {enabled ? "Lock active on next launch" : "Lock disabled"}
        </div>
      )}
    </div>
  );
}

function PromptProfilesSection() {
  const [profiles, setProfiles] = React.useState([]);
  const [activeId, setActiveId] = React.useState("default");
  const [selId, setSelId]       = React.useState("default");
  const [draft, setDraft]       = React.useState("");
  const [status, setStatus]     = React.useState("");
  const [newName, setNewName]   = React.useState("");
  const [naming, setNaming]     = React.useState(false);

  const selected = profiles.find(p => p.id === selId) || profiles.find(p => p.id === "default");
  const isLocked = !!(selected && selected.locked);

  const load = React.useCallback(async () => {
    const d = await window.API.fetchUnleashedProfiles();
    setProfiles(d.profiles || []);
    setActiveId(d.active || "default");
  }, []);
  React.useEffect(() => { load(); }, [load]);
  React.useEffect(() => { if (selected) setDraft(selected.override || ""); }, [selId, profiles]);

  const flash = (m) => { setStatus(m); setTimeout(() => setStatus(""), 2500); };

  async function onSave() {
    if (isLocked) return;
    const r = await window.API.saveUnleashedProfile({ id: selId, name: selected.name, override: draft });
    if (r.status === "saved") { flash("✓ Saved"); await load(); }
    else flash("✗ " + (r.message || "save failed"));
  }
  function onSaveAs() { setNaming(true); }
  async function confirmSaveAs() {
    const name = newName.trim();
    if (!name) { flash("✗ Name required"); return; }
    const r = await window.API.saveUnleashedProfile({ name, override: draft });
    if (r.status === "saved") { setNaming(false); setNewName(""); setSelId(r.id); flash("✓ Created"); await load(); }
    else flash("✗ " + (r.message || "save failed"));
  }
  async function onDelete() {
    if (isLocked) return;
    const r = await window.API.deleteUnleashedProfile(selId);
    if (r.status === "deleted") { setSelId("default"); flash("✓ Deleted"); await load(); }
    else flash("✗ " + (r.message || "delete failed"));
  }
  async function onActivate() {
    const r = await window.API.setActiveUnleashedProfile(selId);
    if (r.status === "saved") { flash("✓ Activated"); await load(); }
    else flash("✗ " + (r.message || "activate failed"));
  }
  function onReset() {
    const def = profiles.find(p => p.id === "default");
    if (def) setDraft(def.override || "");
  }

  return (
    <div style={{ marginTop: 28 }}>
      <div className="mono" style={{ fontSize: 12, color: "var(--cyan)", letterSpacing: "0.22em", fontWeight: 700, marginBottom: 8 }}>
        UNLEASHED PROMPT PROFILES
      </div>
      <div className="mono" style={{ fontSize: 12, color: "var(--ink-4)", maxWidth: 560, marginBottom: 14, lineHeight: 1.5 }}>
        These edit ONLY the Unleashed override layer. Standard Banshee always uses the safe
        Default prompt — it is never changed here. A custom profile only takes effect while
        Unleashed is ON, and the RED Unleashed frame will name it.
      </div>

      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 10 }}>
        <select value={selId} onChange={e => setSelId(e.target.value)}
                className="mono" style={{ fontSize: 13, padding: "6px 8px", background: "var(--bg-2)", color: "var(--ink)", border: "1px solid var(--line)" }}>
          {profiles.map(p => (
            <option key={p.id} value={p.id}>
              {p.name}{p.id === activeId ? "  ● active" : ""}{p.locked ? "  (locked)" : ""}
            </option>
          ))}
        </select>
        <button onClick={onActivate} className="mono"
                style={{ fontSize: 12, padding: "6px 12px", cursor: "pointer", background: "var(--bg-3)", color: "var(--ink)", border: "1px solid var(--line)" }}>
          Set Active
        </button>
      </div>

      <textarea value={draft} onChange={e => setDraft(e.target.value)} readOnly={isLocked}
                rows={10}
                style={{ width: "100%", fontFamily: "monospace", fontSize: 13, lineHeight: 1.5,
                         padding: 10, background: isLocked ? "var(--bg-1)" : "var(--bg-2)",
                         color: "var(--ink)", border: "1px solid var(--line)", resize: "vertical" }} />

      {naming && (
        <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
          <input value={newName} onChange={e => setNewName(e.target.value)} placeholder="Profile name (e.g. My Setting 1)"
                 className="mono" style={{ flex: 1, fontSize: 13, padding: "6px 8px", background: "var(--bg-2)", color: "var(--ink)", border: "1px solid var(--line)" }} />
          <button onClick={confirmSaveAs} className="mono" style={{ fontSize: 12, padding: "6px 12px", cursor: "pointer", background: "var(--buy)", color: "#000", border: "none" }}>Create</button>
          <button onClick={() => setNaming(false)} className="mono" style={{ fontSize: 12, padding: "6px 12px", cursor: "pointer", background: "var(--bg-3)", color: "var(--ink)", border: "1px solid var(--line)" }}>Cancel</button>
        </div>
      )}

      <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
        <button onClick={onSave} disabled={isLocked} className="mono"
                style={{ fontSize: 12, padding: "6px 14px", cursor: isLocked ? "not-allowed" : "pointer",
                         background: "var(--buy)", color: "#000", border: "none", opacity: isLocked ? 0.4 : 1 }}>
          Save
        </button>
        <button onClick={onSaveAs} className="mono"
                style={{ fontSize: 12, padding: "6px 14px", cursor: "pointer", background: "var(--bg-3)", color: "var(--ink)", border: "1px solid var(--line)" }}>
          {isLocked ? "Duplicate to Edit" : "Save As New…"}
        </button>
        <button onClick={onReset} className="mono"
                style={{ fontSize: 12, padding: "6px 14px", cursor: "pointer", background: "var(--bg-3)", color: "var(--ink)", border: "1px solid var(--line)" }}>
          Reset to Default text
        </button>
        <button onClick={onDelete} disabled={isLocked} className="mono"
                style={{ fontSize: 12, padding: "6px 14px", cursor: isLocked ? "not-allowed" : "pointer",
                         background: "transparent", color: "var(--sell)", border: "1px solid var(--sell)", opacity: isLocked ? 0.4 : 1 }}>
          Delete
        </button>
        {status && <span className="mono" style={{ fontSize: 12, alignSelf: "center", color: status.startsWith("✗") ? "var(--sell)" : "var(--buy)" }}>{status}</span>}
      </div>
    </div>
  );
}

function SettingsPage({ onBack }) {
  const [loaded, setLoaded]         = useState(false);
  const [fredKey, setFredKey]       = useState("");
  const [alpacaKey, setAlpacaKey]   = useState("");
  const [alpacaSec, setAlpacaSec]   = useState("");
  const [cgKey, setCgKey]           = useState("");
  const [cgKeyType, setCgKeyType]   = useState("demo");
  const [cgSaveStatus, setCgSaveStatus] = useState(null);
  const [aiType, setAiType]         = useState("Gemini");
  const [aiKey, setAiKey]           = useState("");
  const [aiModel, setAiModel]       = useState("");
  const [aiUrl, setAiUrl]           = useState("");
  const [aiCtxWindow, setAiCtxWindow] = useState(32768);
  const [allowAiRescue, setAllowAiRescue]   = useState(true);
  const [apiSaveStatus, setApiSaveStatus]   = useState(null);
  const [aiSaveStatus, setAiSaveStatus]     = useState(null);
  const [rescueSaveStatus, setRescueSaveStatus] = useState(null);
  const [testStatus, setTestStatus]         = useState(null);
  const [testing, setTesting]               = useState(false);

  useEffect(() => {
    window.API.fetchSettings().then(data => {
      if (!data) { setLoaded(true); return; }
      setFredKey(data.FRED_API?.key || "");
      setAlpacaKey(data.ALPACA_KEY?.key || "");
      setAlpacaSec(data.ALPACA_SECRET?.key || "");
      setCgKey(data.COINGECKO?.key || "");
      setCgKeyType(data.COINGECKO?.key_type || "demo");
      const ai = data.AI_API || {};
      setAiType(ai.type || "Gemini");
      setAiKey(ai.key || "");
      setAiModel(ai.model || "");
      setAiUrl(ai.url || "");
      setAiCtxWindow(ai.context_window || 32768);
      setAllowAiRescue(data.allow_ai_data_rescue !== false);
      setLoaded(true);
    });
  }, []);

  async function saveAPIKeys() {
    setApiSaveStatus("saving");
    const result = await window.API.saveSettings({
      FRED_API:      { key: fredKey },
      ALPACA_KEY:    { key: alpacaKey },
      ALPACA_SECRET: { key: alpacaSec },
    });
    setApiSaveStatus(result.status === "saved" ? "saved" : "error: " + (result.message || "?"));
    setTimeout(() => setApiSaveStatus(null), 3000);
  }

  async function saveAIBrain() {
    setAiSaveStatus("saving");
    const result = await window.API.saveSettings({
      AI_API: { type: aiType, key: aiKey, model: aiModel, url: aiUrl, context_window: aiCtxWindow },
    });
    setAiSaveStatus(result.status === "saved" ? "saved" : "error: " + (result.message || "?"));
    setTimeout(() => setAiSaveStatus(null), 3000);
  }

  async function saveCgKey() {
    const result = await window.API.saveSettings({ COINGECKO: { key: cgKey, key_type: cgKeyType } });
    setCgSaveStatus(result?.status === "saved" ? "✓ SAVED" : "✗ save failed");
    setTimeout(() => setCgSaveStatus(null), 2000);
  }

  async function saveDataRecovery() {
    setRescueSaveStatus("saving");
    const result = await window.API.saveSettings({ allow_ai_data_rescue: allowAiRescue });
    setRescueSaveStatus(result.status === "saved" ? "saved" : "error: " + (result.message || "?"));
    setTimeout(() => setRescueSaveStatus(null), 3000);
  }

  async function handleTest() {
    setTesting(true); setTestStatus(null);
    const result = await window.API.testAIConnection({ type: aiType, key: aiKey, model: aiModel, url: aiUrl });
    setTesting(false);
    setTestStatus(result);
  }

  const needsUrl = aiType === "Ollama" || aiType === "Custom";

  const DEFAULT_MODELS = {
    Gemini:    "gemini-2.5-flash",
    OpenAI:    "gpt-4o-mini",
    Anthropic: "claude-sonnet-4-6",
    Ollama:    "llama3",
    Custom:    "",
  };

  return (
    <div style={{ position: "absolute", inset: 0, background: "var(--bg-1)", display: "flex", flexDirection: "column", zIndex: 30, animation: "fadeIn 200ms ease" }}>

      {/* header */}
      <div style={{ height: 52, padding: "0 18px", flex: "0 0 auto", borderBottom: "1px solid var(--line)", display: "flex", alignItems: "center", gap: 18, background: "var(--bg-2)" }}>
        <button onClick={onBack} style={{ display: "flex", alignItems: "center", gap: 6, padding: "6px 10px", background: "transparent", border: "1px solid var(--line-2)", color: "#FF6D00", cursor: "pointer" }}>
          <svg width="10" height="10" viewBox="0 0 10 10"><path d="M7 1 L3 5 L7 9" stroke="currentColor" strokeWidth="1.5" fill="none"/></svg>
          <span className="mono" style={{ fontSize: 13, letterSpacing: "0.16em" }}>BACK</span>
        </button>
        <span className="mono" style={{ fontSize: 14, fontWeight: 700, letterSpacing: "0.18em", color: "var(--ink)" }}>SETTINGS</span>
        <span className="mono" style={{ fontSize: 12, color: "var(--ink-4)", letterSpacing: "0.14em" }}>BANSHEE 5 CONFIGURATION</span>
      </div>

      {/* scrollable content */}
      <div style={{ flex: 1, overflowY: "auto", padding: "24px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, alignContent: "start" }}>

        {/* DATA SOURCES — full width */}
        <div style={{ gridColumn: "1 / -1" }}>
          <DataSourcesSection
            cgKey={cgKey}
            onCgKeyChange={setCgKey}
            cgKeyType={cgKeyType}
            onCgKeyTypeChange={setCgKeyType}
            onSaveCgKey={saveCgKey}
            saveStatus={cgSaveStatus}
            onSettingsSave={async (partial) => {
              await window.API.saveSettings(partial);
            }}
          />
        </div>

        {/* API KEYS */}
        <SettingsSection title="▸ API KEYS">
          {!loaded ? (
            <span className="mono" style={{ fontSize: 13, color: "var(--ink-4)" }}>LOADING…</span>
          ) : (<>
            <SettingsField label="FRED API KEY" hint="macroeconomic data">
              <input
                value={fredKey} onChange={e => setFredKey(e.target.value)}
                placeholder="paste key here…" style={INPUT_STYLE}
              />
            </SettingsField>
            <SettingsField label="ALPACA API KEY" hint="equity feeds + paper trading">
              <input
                value={alpacaKey} onChange={e => setAlpacaKey(e.target.value)}
                placeholder="paste key here…" style={INPUT_STYLE}
              />
            </SettingsField>
            <SettingsField label="ALPACA SECRET">
              <input
                type="password"
                value={alpacaSec} onChange={e => setAlpacaSec(e.target.value)}
                placeholder="paste secret here…" style={INPUT_STYLE}
              />
            </SettingsField>
            <div style={{ padding: "10px 12px", background: "rgba(56,189,248,0.04)", border: "1px solid var(--line)", marginBottom: 16 }}>
              <span className="mono" style={{ fontSize: 12, color: "var(--ink-3)", letterSpacing: "0.12em", lineHeight: 1.6 }}>
                CRYPTO FEEDS — auto via CCXT (no key needed)<br/>
                EQUITY FEEDS — via Alpaca key above<br/>
                MACRO — via FRED key above
              </span>
            </div>
            <SaveRow onSave={saveAPIKeys} status={apiSaveStatus} />
          </>)}
        </SettingsSection>

        {/* AI BRAIN */}
        <SettingsSection title="▸ AI BRAIN">
          {!loaded ? (
            <span className="mono" style={{ fontSize: 13, color: "var(--ink-4)" }}>LOADING…</span>
          ) : (<>
            <SettingsField label="PROVIDER">
              <select value={aiType} onChange={e => { setAiType(e.target.value); setAiModel(DEFAULT_MODELS[e.target.value] || ""); }} style={SELECT_STYLE}>
                {AI_PROVIDERS.map(p => <option key={p} value={p}>{p}</option>)}
              </select>
            </SettingsField>
            <SettingsField label="MODEL NAME">
              <input
                value={aiModel} onChange={e => setAiModel(e.target.value)}
                placeholder={DEFAULT_MODELS[aiType] || "model name…"} style={INPUT_STYLE}
              />
            </SettingsField>
            <SettingsField label="API KEY" hint={aiType === "Ollama" ? "not required for local" : ""}>
              <input
                type="password"
                value={aiKey} onChange={e => setAiKey(e.target.value)}
                placeholder={aiType === "Ollama" ? "not needed for local Ollama" : "paste API key here…"}
                disabled={aiType === "Ollama"}
                style={{ ...INPUT_STYLE, opacity: aiType === "Ollama" ? 0.4 : 1 }}
              />
            </SettingsField>
            {needsUrl && (
              <SettingsField label="BASE URL" hint="e.g. http://100.x.x.x:11434 for Tailscale">
                <input
                  value={aiUrl} onChange={e => setAiUrl(e.target.value)}
                  placeholder="http://localhost:11434" style={INPUT_STYLE}
                />
              </SettingsField>
            )}
            {aiType === "Ollama" && (
              <SettingsField label="CONTEXT WINDOW" hint="tokens — 32768 for Gemma 4, min supported">
                <input
                  type="number" min="32768" step="1024"
                  value={aiCtxWindow} onChange={e => setAiCtxWindow(parseInt(e.target.value) || 32768)}
                  style={INPUT_STYLE}
                />
              </SettingsField>
            )}

            {/* test connection */}
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
              <button onClick={handleTest} disabled={testing} style={{
                padding: "7px 18px",
                background: testing ? "var(--bg-3)" : "rgba(56,189,248,0.12)",
                color: testing ? "var(--ink-4)" : "var(--cyan)",
                border: "1px solid var(--cyan)", cursor: testing ? "default" : "pointer",
                fontFamily: "'JetBrains Mono', monospace", fontSize: 13, fontWeight: 700, letterSpacing: "0.18em",
              }}>
                {testing ? "TESTING…" : "TEST CONNECTION"}
              </button>
              {testStatus && (
                <span className="mono" style={{
                  fontSize: 13, letterSpacing: "0.1em",
                  color: testStatus.status === "ok" ? "var(--buy)" : "var(--sell)",
                }}>
                  {testStatus.status === "ok" ? `✓ OK — ${testStatus.message}` : `✗ ${testStatus.message}`}
                </span>
              )}
            </div>

            <SaveRow onSave={saveAIBrain} status={aiSaveStatus} />
          </>)}
        </SettingsSection>

        {/* DATA RECOVERY */}
        <SettingsSection title="▸ DATA RECOVERY">
          <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 0" }}>
            <input
              type="checkbox"
              id="ai-rescue-toggle"
              checked={allowAiRescue}
              onChange={e => setAllowAiRescue(e.target.checked)}
              style={{ accentColor: "#FF6D00", width: 16, height: 16, cursor: "pointer" }}
            />
            <label
              htmlFor="ai-rescue-toggle"
              style={{ color: "var(--ink)", fontSize: 12, fontFamily: "monospace", cursor: "pointer" }}
            >
              ALLOW AI TO SELF-HEAL DATA FORMAT CHANGES
            </label>
          </div>
          <div style={{ color: "var(--ink-3)", fontSize: 11, marginTop: 4 }}>
            When yfinance returns unexpected column names, calls your AI to remap them.
            Disable to prevent unintended AI usage during data outages.
          </div>
          <SaveRow onSave={saveDataRecovery} status={rescueSaveStatus} />
        </SettingsSection>

        {/* PIN LOCK */}
        <SettingsSection title="▸ PIN LOCK">
          <PinSettings />
        </SettingsSection>

        {/* MCP CONNECTION — full width */}
        <div style={{ gridColumn: "1 / -1" }}>
          <SettingsSection title="▸ MCP CONNECTION">
            <MCPConnectionBlock />
          </SettingsSection>
        </div>

        {/* UNLEASHED PROMPT PROFILES — full width */}
        <div style={{ gridColumn: "1 / -1" }}>
          <PromptProfilesSection />
        </div>

      </div>
    </div>
  );
}

export default SettingsPage;
