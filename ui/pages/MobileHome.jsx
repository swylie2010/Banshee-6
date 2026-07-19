/* ui/pages/MobileHome.jsx
 * Phone landing: one scrollable column you thumb down. Desktop is unaffected —
 * this only renders below the mobile breakpoint (App decides). Sections are
 * added in later tasks; this task just proves the seam and scroll container. */
function MobileHome({ macroData, radarData, snapshot, watchlist, onOpenSymbol, onSearch, onNav }) {
  return (
    <div style={{
      height: "100%", overflowY: "auto", WebkitOverflowScrolling: "touch",
      background: "var(--bg-0)", padding: "10px 12px 40px",
    }}>
      <div className="mono" style={{ fontSize: 12, color: "var(--ink-3)" }}>
        MobileHome scaffold — sections coming
      </div>
    </div>
  );
}

export default MobileHome;
