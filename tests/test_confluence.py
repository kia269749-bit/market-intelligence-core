from mi_core.confluence import confluence_score


def test_confluence_rewards_multi_layer_agreement():
    report = confluence_score(0.8, 0.7, 0.6, 0.5, 0.7)
    assert report["bias"] == "BULLISH"
    assert report["score"] > 0.20
    assert report["agreement"] == 1.0
    assert report["diagnostic_only"] is True


def test_confluence_exposes_conflict():
    report = confluence_score(0.8, -0.8, 0.0, -0.4, 0.7)
    assert report["agreement"] < 1.0


def test_confluence_conflict_penalty_reduces_effective_score():
    report = confluence_score(0.8, -0.8, 0.0, -0.4, 0.7)
    assert report["conflict_penalty"] > 0.0
    assert abs(report["effective_score"]) < abs(report["score"])
    assert report["effective_bias"] == "NEUTRAL"
