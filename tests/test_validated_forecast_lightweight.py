from dataclasses import replace

from mi_core.models import MarketBar
from mi_core.validated_forecast import _feat, _feature_cache, walk_forward_forecast


def _bars(n=140):
    rows = []
    price = 100.0
    for i in range(n):
        price *= 1.0 + (0.0008 if i % 7 < 4 else -0.0005)
        rows.append(
            MarketBar(
                ts=i,
                symbol="BTC",
                price=price,
                volume=1000.0 + i,
                oi=5000.0 + i * 2,
                funding=0.00001,
                buy_volume=60.0 + (i % 5),
                sell_volume=40.0 + (i % 3),
            )
        )
    return rows


def test_feature_cache_matches_original_feature_values():
    bars = _bars()
    cache = _feature_cache(bars)
    for i in range(20, len(bars)):
        old = _feat(bars, i)
        new = cache[i]
        assert new is not None
        assert len(old) == len(new)
        for a, b in zip(old, new):
            assert abs(a - b) < 1e-10


def test_walk_forward_uses_cached_features_and_stays_research_only():
    result = walk_forward_forecast(
        _bars(),
        horizon=5,
        train_window=60,
        min_train=60,
        fit_every=10,
    )
    assert result["available"] is True
    assert result["predictions"]
    assert result["research_only"] is True
    assert result["live_orders"] is False

def test_future_suffix_mutation_does_not_change_prior_predictions():
    bars = _bars(220)
    cut = 155
    baseline = walk_forward_forecast(
        bars, horizon=5, train_window=100, min_train=60, fit_every=10
    )
    altered = list(bars)
    for i in range(cut + 1, len(altered)):
        altered[i] = replace(altered[i], price=altered[i].price * (1.0 + 0.03))
    changed = walk_forward_forecast(
        altered, horizon=5, train_window=100, min_train=60, fit_every=10
    )

    def prefix(rows):
        return [
            (r["ts"], r["pred"], r["p_up"], r["p_flat"], r["p_down"])
            for r in rows if r["ts"] <= cut
        ]

    assert prefix(baseline["predictions"]) == prefix(changed["predictions"])


def test_missing_derivatives_are_explicit_features_and_reported():
    bars = _bars(140)
    missing = [
        MarketBar(
            ts=b.ts, symbol=b.symbol, price=b.price, volume=b.volume,
            oi=None, funding=None, buy_volume=b.buy_volume, sell_volume=b.sell_volume,
        )
        for b in bars
    ]
    feature = _feat(missing, 50)
    assert feature[-2:] == [0.0, 0.0]

    result = walk_forward_forecast(
        missing, horizon=5, train_window=60, min_train=60, fit_every=10
    )
    coverage = result["feature_data_coverage"]
    assert coverage["oi"]["present"] == 0
    assert coverage["oi"]["coverage"] == 0.0
    assert coverage["funding"]["present"] == 0
    assert coverage["funding"]["coverage"] == 0.0
