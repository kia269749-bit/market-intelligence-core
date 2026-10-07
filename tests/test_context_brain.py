from mi_core.context_brain import analyze_market_context
from mi_core.models import MarketBar


def _bars(symbol, prices, start=1_700_000_000_000):
    return [
        MarketBar(ts=start + i * 60_000, symbol=symbol, price=price)
        for i, price in enumerate(prices)
    ]


def test_context_detects_positive_negative_relationships_and_breadth():
    btc = [100 + i for i in range(30)]
    eth = [50 + 2 * i for i in range(30)]
    xrp = [100 - i for i in range(30)]
    doge = [20 + (i if i % 2 else -i * 0.1) for i in range(30)]
    out = analyze_market_context(
        {"BTC": _bars("BTC", btc), "ETH": _bars("ETH", eth),
         "XRP": _bars("XRP", xrp), "DOGE": _bars("DOGE", doge)}
    )
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
