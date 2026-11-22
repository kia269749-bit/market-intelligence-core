from mi_core.brains.contracts import BrainProposal, MarketSnapshot
from mi_core.brains.orchestrator import arbitrate

def p(brain, family, direction, ts=100_000, confidence=0.8):
    return BrainProposal(brain, family, direction, confidence, ts, (brain,), ("test",))

def test_two_independent_families_can_signal_long():
    result = arbitrate(MarketSnapshot("BTC", 100_000, "1h"), [p("ta", "technical", "LONG"), p("flow", "orderflow", "LONG")])
    assert result.decision == "LONG" and result.live_orders is False

def test_same_family_duplicates_count_once():
    result = arbitrate(MarketSnapshot("BTC", 100_000, "1h"), [p("rsi", "technical", "LONG"), p("macd", "technical", "LONG")])
    assert result.decision == "NO_TRADE"
    assert "insufficient_independent_brain_families" in result.reasons

def test_stale_or_future_proposals_are_ignored():
    result = arbitrate(MarketSnapshot("BTC", 100_000, "1h"), [p("ta", "technical", "LONG", 1), p("flow", "orderflow", "LONG", 100_001)])
    assert result.decision == "NO_TRADE"

def test_win_rate_is_shrunk_for_small_samples():
    stats = {"ta": {"wins": 1, "losses": 0}, "flow": {"wins": 1, "losses": 0}}
    result = arbitrate(MarketSnapshot("BTC", 100_000, "1h"), [p("ta", "technical", "LONG"), p("flow", "orderflow", "LONG")], stats)
    assert result.decision == "LONG"
    assert all(v["performance_weight"] < 1.0 for v in result.votes)
