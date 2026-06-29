import micro_engine as me

EQ_READY   = {"quality": "READY",   "reasons": ["All timing conditions are clear."]}
EQ_WAIT_OS = {"quality": "WAIT",    "reasons": ["Stoch RSI is already oversold for shorts."]}


def test_htf_bearish_ltf_short_is_aligned():
    r = me.compute_bias_trigger_alignment(
        "DOWNTREND", "DOWNTREND", "DOWNTREND",
        s_bull=0, s_bear=3, m_bull=0, m_bear=3, f_bull=0, f_bear=3,
        entry_quality=EQ_READY,
    )
    assert r["bias"]["direction"] == "BEARISH"
    assert r["trigger"]["direction"] == "SHORT"
    assert r["alignment"] == "aligned"


def test_htf_bearish_ltf_long_is_conflict():
    r = me.compute_bias_trigger_alignment(
        "DOWNTREND", "DOWNTREND", "UPTREND",
        s_bull=0, s_bear=3, m_bull=0, m_bear=3, f_bull=3, f_bear=0,
        entry_quality=EQ_READY,
    )
    assert r["bias"]["direction"] == "BEARISH"
    assert r["trigger"]["direction"] == "LONG"
    assert r["alignment"] == "conflict"


def test_neutral_bias_yields_neutral_alignment():
    r = me.compute_bias_trigger_alignment(
        "RANGE", "RANGE", "DOWNTREND",
        s_bull=1, s_bear=1, m_bull=1, m_bear=1, f_bull=0, f_bear=2,
        entry_quality=EQ_READY,
    )
    assert r["bias"]["direction"] == "NEUTRAL"
    assert r["alignment"] == "neutral"


def test_extended_in_trend_short_carries_both_readings():
    # downtrend short that is already oversold = extended IN the trend direction
    r = me.compute_bias_trigger_alignment(
        "DOWNTREND", "DOWNTREND", "DOWNTREND",
        s_bull=0, s_bear=3, m_bull=0, m_bear=3, f_bull=0, f_bear=3,
        entry_quality=EQ_WAIT_OS,
    )
    ext = r["trigger"]["extended_reading"]
    assert ext["extended"] is True
    assert ext["in_trend"] is True
    assert ext["momentum_note"]        # non-empty: the "kill is live" reading
    assert ext["mean_reversion_note"]  # non-empty: the bounce-risk reading
