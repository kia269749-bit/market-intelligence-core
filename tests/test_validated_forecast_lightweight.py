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
