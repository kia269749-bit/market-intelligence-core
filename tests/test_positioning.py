from mi_core.positioning import analyze_positioning


def test_positioning_bullish_derivatives_snapshot():
    report = analyze_positioning({
        "oi_change_pct": 3.0,
        "funding": -0.0002,
        "long_short_ratio": 1.4,
        "taker_buy": 700,
        "taker_sell": 300,
        "basis_pct": 0.1,
        "liquidation_long": 10,
        "liquidation_short": 100,
        "liquidation_threshold": 50,
    })
    assert report["bias"] == "BULLISH"
    assert report["positioning_score"] > 0.20
    assert report["liquidations"]["bias"] == "SHORT_LIQUIDATION"
    assert report["liquidations"]["cascade_risk"] is True
    assert report["diagnostic_only"] is True


def test_positioning_neutral_without_derivatives_data():
    report = analyze_positioning({})
    assert report["bias"] == "NEUTRAL"
    assert report["positioning_score"] == 0.0
    assert report["liquidations"]["cascade_risk"] is False
