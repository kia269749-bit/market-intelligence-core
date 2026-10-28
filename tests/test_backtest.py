from mi_core.backtest import run
from mi_core.costs import ROUND_TRIP_COST_PCT
from mi_core.models import MarketBar, Signal


def _bars():
    return [MarketBar(ts=i, symbol="BTCUSDT", price=100 + i * 2) for i in range(8)]


def test_backtest_reports_research_metrics_and_costs():
    bars = _bars()
    signals = [
        Signal(ts=i, symbol="BTCUSDT", side="LONG" if i == 0 else "FLAT",
               score=0.8 if i == 0 else 0.0, regime="BULL")
        for i in range(len(bars))
    ]
    result = run(bars, signals, fee_bps=5, slippage_bps=3, latency_bars=1, hold_bars=2)
    assert result["research_only"] is True
    assert result["live_orders"] is False
    assert result["trades_count"] == 1
    assert result["wins"] == 1
    assert result["win_rate"] == 1.0
    assert result["gross_profit"] > 0
    assert result["cost_total"] > 0
    assert result["profit_factor"] > 0
    assert result["cost_model"] == "legacy_fee_slippage_override"
    assert result["round_trip_cost_pct"] is None


def test_default_backtest_uses_central_round_trip_cost():
    bars = _bars()
    signals = [
        Signal(ts=i, symbol="BTCUSDT", side="LONG" if i == 0 else "FLAT",
               score=0.8 if i == 0 else 0.0, regime="BULL")
        for i in range(len(bars))
    ]
    result = run(bars, signals, latency_bars=1, hold_bars=2)
    assert abs(result["cost_total"] - 1000.0 * ROUND_TRIP_COST_PCT / 100.0) < 1e-9
    assert result["cost_model"] == "fixed_aggregate_round_trip"
    assert result["round_trip_cost_pct"] == ROUND_TRIP_COST_PCT

def test_backtest_rejects_unsafe_configuration():
    bars = _bars()
    signals = [Signal(i, "BTCUSDT", "FLAT", 0.0, "RANGE") for i in range(len(bars))]
    try:
        run(bars, signals, risk_fraction=0)
    except ValueError:
        pass
    else:
        raise AssertionError("expected invalid risk_fraction to fail")


def test_backtest_cost_sensitivity_uses_exact_round_trip_rate():
    bars = _bars()
    signals = [
        Signal(ts=i, symbol="BTCUSDT", side="LONG" if i == 0 else "FLAT",
               score=0.8 if i == 0 else 0.0, regime="BULL")
        for i in range(len(bars))
    ]
    # A $1,000 entry notional makes percentage-to-dollar cost conversion explicit.
    for rate_pct, expected_cost in ((0.24, 2.40), (0.12, 1.20), (0.04, 0.40)):
        result = run(bars, signals, initial=10000.0, risk_fraction=0.1,
                     round_trip_cost_pct=rate_pct, latency_bars=1, hold_bars=2)
        assert result["cost_model"] == "fixed_aggregate_round_trip"
        assert result["round_trip_cost_pct"] == rate_pct
        assert abs(result["cost_total"] - expected_cost) < 1e-9


def test_legacy_model_does_not_claim_aggregate_rate_even_if_supplied():
    bars = _bars()
    signals = [
        Signal(ts=i, symbol="BTCUSDT", side="LONG" if i == 0 else "FLAT",
               score=0.8 if i == 0 else 0.0, regime="BULL")
        for i in range(len(bars))
    ]
    result = run(bars, signals, fee_bps=5, slippage_bps=3,
                 round_trip_cost_pct=0.24, latency_bars=1, hold_bars=2)
    assert result["cost_model"] == "legacy_fee_slippage_override"
    assert result["round_trip_cost_pct"] is None
    assert result["cost_total"] > 0
