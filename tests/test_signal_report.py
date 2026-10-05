from mi_core.signal_report import build_signal_report, render_signal_report


def _sample_report():
    return build_signal_report(
        symbol="BTCUSDT",
        signal={"side": "LONG", "score": 0.9},
        signal_summary={
            "direction": "LONG", "status": "STRONG", "conviction": 0.82,
            "warnings": (), "manual_review": True,
        },
        flow={"bias": "BULLISH", "smart_money_score": 0.8},
        positioning={"bias": "BULLISH"},
        microstructure={"bias": "BULLISH"},
        cross_exchange={"bias": "BULLISH", "confirmed": True},
        confluence={"effective_score": 0.85, "agreement": 1.0},
        crowding={"level": "NORMAL", "score": 0.1, "cascade_risk": False},
    )


def test_final_signal_report_is_manual_and_research_only():
    report = _sample_report()
    assert report["direction"] == "LONG"
    assert report["status"] == "STRONG"
    assert report["conviction_pct"] == 82.0
    assert report["confirmations"] >= 4
    assert report["conflicts"] == 0
    assert report["cross_exchange_confirmed"] is True
    assert report["confirmations"] == 5
    assert report["risk_level"] == "LOW"
    assert report["decision"] == "MANUAL_REVIEW_REQUIRED"
    assert report["manual_review"] is True
    assert report["research_only"] is True
    assert report["live_orders"] is False


def test_final_signal_report_surfaces_risk_warnings():
    report = build_signal_report(
        symbol="BTCUSDT",
        signal={"side": "SHORT", "score": 0.7},
        signal_summary={
            "direction": "SHORT", "status": "WATCH", "conviction": 0.61,
            "warnings": ("EXTREME_CROWDING", "LIQUIDATION_CASCADE_RISK"),
            "manual_review": True,
        },
        flow={"bias": "BULLISH", "smart_money_score": 0.4},
        positioning={"bias": "SHORT"},
        microstructure={"bias": "SHORT"},
        cross_exchange={"bias": "SHORT", "confirmed": False},
        confluence={"effective_score": -0.7, "agreement": 0.75},
        crowding={"level": "EXTREME", "score": 0.9, "cascade_risk": True},
    )
    assert "EXTREME_CROWDING" in report["warnings"]
    assert "LIQUIDATION_CASCADE_RISK" in report["warnings"]
    assert report["conflicts"] >= 1
    assert report["risk_level"] == "HIGH"
    assert report["decision"] == "MANUAL_REVIEW_REQUIRED"
    assert report["manual_review"] is True


def test_render_signal_report_is_deterministic_and_safe():
    rendered = render_signal_report(_sample_report())
    assert "BTCUSDT" in rendered
    assert "Direction: LONG" in rendered
    assert "Conviction: 82.00%" in rendered
    assert "Decision: MANUAL_REVIEW_REQUIRED" in rendered
    assert "Research Only: YES" in rendered
    assert "Live Orders: NO" in rendered
    assert "Cross-Exchange: True [YES]" in rendered
