import math

from mi_core.context_brain import analyze_market_context
from mi_core.models import MarketBar


def _bars(symbol, prices, start=1_700_000_000_000):
    return [
        MarketBar(ts=start + i * 60_000, symbol=symbol, price=price)
        for i, price in enumerate(prices)
    ]


def _bars_from_log_returns(symbol, returns, start_price=100.0):
    prices = [start_price]
    for ret in returns:
        prices.append(prices[-1] * math.exp(ret))
    return _bars(symbol, prices)


def test_context_detects_positive_negative_relationships_and_breadth():
    # Correlation is computed on returns, so construct actual positive and
    # inverse return series instead of assuming opposite price-level trends
    # imply negatively correlated returns.
    btc_returns = [0.012 if i % 2 == 0 else -0.004 for i in range(29)]
    eth_returns = [r * 1.4 for r in btc_returns]
    xrp_returns = [-r for r in btc_returns]
    doge_returns = [0.008 if i % 3 else -0.001 for i in range(29)]
    out = analyze_market_context({
        "BTC": _bars_from_log_returns("BTC", btc_returns),
        "ETH": _bars_from_log_returns("ETH", eth_returns, 50.0),
        "XRP": _bars_from_log_returns("XRP", xrp_returns),
        "DOGE": _bars_from_log_returns("DOGE", doge_returns, 20.0),
    })
    assert out["available"] is True
    assert out["relationships"]["correlations"]["ETH"]["relationship"] == "POSITIVE"
    assert out["relationships"]["correlations"]["XRP"]["relationship"] == "NEGATIVE"
    assert out["breadth"]["breadth_state"] in ("BROAD_UP", "MIXED")


def test_context_exposes_session_and_research_only_policy():
    bars = _bars("BTC", [100 + i for i in range(20)])
    out = analyze_market_context({"BTC": bars})
    assert out["available"] is True
    assert out["session"] in {
        "ASIA", "LONDON", "LONDON_NY_OVERLAP", "NEW_YORK", "POST_NY"
    }
    assert out["research_only"] is True
    assert out["live_orders"] is False


def test_context_requires_reference_history():
    out = analyze_market_context({"BTC": _bars("BTC", [100 + i for i in range(5)])})
    assert out["available"] is False
    assert out["reason"] == "insufficient_reference_history"
