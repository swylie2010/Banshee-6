# Banshee Pro 4 — Wiki Index

Single source of truth for the project. Lives in the project folder so any AI can read it.

## Memory Model

| Tier | File | Purpose | When to Read |
|------|------|---------|--------------|
| Semantic (Wiki) | `wiki/` ← you are here | Current state, architecture, design decisions | Session start, or when lost |
| Working (Focus) | `ACTIVE_TASK.md` | One task at a time, scoped for a fresh agent | Every session start |
| Episodic (Diary) | Claude memory: `Banshee_Running_Notes.md` | Append-only history of discussions | Only when deeply lost |
| Procedural (Playbooks) | `wiki/03_PLAYBOOKS.md` | Step-by-step repeatable procedures | When executing a known procedure |
| Aversive (Anti-patterns) | `wiki/04_ANTI_PATTERNS.md` | What not to do and why | When about to do something risky |

## Wiki Pages

- **[01_ARCHITECTURE](01_ARCHITECTURE.md)** — Three-layer design, file map, ports, MCP config, engine inventory
- **[02_DATA_AND_ASSETS](02_DATA_AND_ASSETS.md)** — Data sources, asset profiles, htf_levels, TV OHLCV files
- **[03_PLAYBOOKS](03_PLAYBOOKS.md)** — Calibration, TV connection, new-machine setup, adding assets
- **[04_ANTI_PATTERNS](04_ANTI_PATTERNS.md)** — What we tried that failed or must never be repeated
- **[05_OPENCLAW_VISION](05_OPENCLAW_VISION.md)** — The longer-horizon AI agent goal and build order

## Also Read
- `OPERATIONAL_GUIDE.md` (project root) — Plain-English SMC concepts, chart reading workflow, visual encoding
