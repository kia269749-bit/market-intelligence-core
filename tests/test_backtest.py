from mi_core.backtest import run
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


def test_backtest_rejects_unsafe_configuration():
    bars = _bars()
    signals = [Signal(i, "BTCUSDT", "FLAT", 0.0, "RANGE") for i in range(len(bars))]
    try:
        run(bars, signals, risk_fraction=0)
    except ValueError:
        pass
    else:
        raise AssertionError("expected invalid risk_fraction to fail")
