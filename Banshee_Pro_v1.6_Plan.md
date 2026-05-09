# Banshee Pro v1.6 — The Precision Update

This implementation plan covers the next phase of updates, focusing on edge-case CSS corrections and restoring the exact institutional trading plans from Wily Pro.

## User Review Required

> [!IMPORTANT]
> The plan below incorporates the ATR setup logic exactly as requested. Please review the plan. If you approve, I will execute these changes immediately!

## Proposed Changes

---
### 1. Deep CSS Selectbox Fixes

#### [MODIFY] `app.py`
- We successfully fixed the collapsed state of the dropdowns, but the expanded menu (the actual list of options) inherits from Streamlit's Baseweb global overlay (`[data-baseweb="popover"]` and `ul[role="listbox"]`).
- We will add specific CSS targeting the dropdown popovers and expanders to force them into the light blue/crisp white backgrounds with strictly dark text, overriding the deep Streamlit defaults completely.

---
### 2. The Institutional ATR Trade Plan

#### [MODIFY] `app.py`
- **Asset Radar & Banshee Nexus Tabs:** We will bring over the full `ATR-Based Trade Plan` from Wily Trading Pro.
- This feature dynamically calculates the institutional risk-reward boundaries based on the **Average True Range (ATR)** of the specific asset. 
- It will explicitly render:
    - Entry price.
    - Stop-Loss levels (Long and Short) placed mathematically out of normal noise ranges.
    - Target levels (Long and Short).
    - Risk:Reward Validation (ensuring the classic "GOOD 2.0:1" threshold is met).
- This block will exist seamlessly beneath the Signal Breakdown expander in both views.

## Verification Plan

### Automated Tests
- Re-compile `app.py` to ensure Streamlit syntax remains uncorrupted.

### Manual Verification
1. Click any dropdown selector (like Trading Mode) and verify the populating list is fully readable.
2. Select "Banshee Nexus" and confirm that a new section titled **📐 ATR-Based Trade Plan** beautifully renders the entry, stop, target, and risk ratios.
