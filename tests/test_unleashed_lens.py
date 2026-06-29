import micro_engine as me


def test_deadzone_stays_wait_when_conservative():
    # mixed HTF (range) + actionable LTF short -> conservative naturally WAITs
    v, *_ = me.compute_verdict(
        "RANGE", "RANGE", "DOWNTREND",
        s_bull=1, s_bear=1, m_bull=1, m_bear=1, f_bull=0, f_bear=2,
        unleashed=False,
    )
    assert v == "WAIT — NO TRADE"


def test_deadzone_surfaces_trigger_when_unleashed():
    # same inputs, unleashed -> the buried LTF short Trigger is surfaced
    v, *_ = me.compute_verdict(
        "RANGE", "RANGE", "DOWNTREND",
        s_bull=1, s_bear=1, m_bull=1, m_bear=1, f_bull=0, f_bear=2,
        unleashed=True,
    )
    assert v == "SELL SETUP"


def test_conservative_conflict_verdict_unchanged():
    # HTF strongly bearish + LTF bull bounce: conservative must KEEP its directional
    # verdict (NOT collapse to WAIT). Guards the byte-identical-when-off contract.
    v, *_ = me.compute_verdict(
        "DOWNTREND", "DOWNTREND", "UPTREND",
        s_bull=0, s_bear=3, m_bull=0, m_bear=3, f_bull=3, f_bear=0,
        unleashed=False,
    )
    assert v in ("SELL SETUP", "STRONG SELL")


def test_entry_gate_vetoes_extended_short_when_conservative():
    import pandas as pd, numpy as np
    fast = pd.DataFrame({"stoch_k": [10.0], "rsi": [45.0]})  # oversold k<25
    q = me.compute_entry_quality("SELL SETUP", fast, slow_adx=30, funding={}, unleashed=False)
    assert q["quality"] == "WAIT"


def test_entry_gate_does_not_veto_extended_in_trend_short_when_unleashed():
    import pandas as pd
    fast = pd.DataFrame({"stoch_k": [10.0], "rsi": [45.0]})
    q = me.compute_entry_quality("SELL SETUP", fast, slow_adx=30, funding={}, unleashed=True)
    assert q["quality"] != "WAIT"   # momentum confirmation, not a veto


def test_adx_chop_demotes_when_conservative_only():
    cons, *_ = me.compute_verdict("UPTREND", "UPTREND", "UPTREND",
                                  s_bull=4, s_bear=0, m_bull=4, m_bear=0, f_bull=4, f_bear=0,
                                  slow_adx=15, unleashed=False)
    unl, *_  = me.compute_verdict("UPTREND", "UPTREND", "UPTREND",
                                  s_bull=4, s_bear=0, m_bull=4, m_bear=0, f_bull=4, f_bear=0,
                                  slow_adx=15, unleashed=True)
    assert cons == "BUY SETUP"     # demoted from STRONG by ADX<20
    assert unl  == "STRONG BUY"    # not demoted under unleashed
