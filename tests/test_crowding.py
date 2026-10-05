from mi_core.crowding import analyze_crowding


def test_crowding_detects_stretched_positioning():
    report = analyze_crowding({
        "funding": 0.001,
        "oi_change_pct": 5.0,
        "long_short_ratio": 2.0,
        "liquidation_long": 20,
        "liquidation_short": 100,
        "liquidation_threshold": 50,
    })
    assert report["level"] in {"ELEVATED", "EXTREME"}
    assert report["oi_funding_divergence"] is True
    assert report["cascade_risk"] is True
    assert report["diagnostic_only"] is True


def test_crowding_is_normal_without_derivatives_data():
    report = analyze_crowding({})
    assert report["level"] == "NORMAL"
    assert report["score"] == 0.0
    assert report["cascade_risk"] is False
