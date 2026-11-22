import pandas as pd

from mi_core.indicator_brain import evaluate_indicator_brain


def test_indicator_brain_rejects_non_dataframe():
    result = evaluate_indicator_brain([])
    assert result["available"] is False
    assert result["reason"] == "ohlcv_must_be_dataframe"


def test_indicator_brain_reports_missing_ohlcv_columns():
    frame = pd.DataFrame({"close": [100.0] * 100})
    result = evaluate_indicator_brain(frame)
    assert result["available"] is False
    assert result["reason"] == "missing_ohlcv_columns"
    assert set(result["missing"]) == {"open", "high", "low", "volume"}


def test_indicator_brain_requires_sufficient_completed_bars():
    frame = pd.DataFrame({
        "open": [100.0] * 20,
        "high": [101.0] * 20,
        "low": [99.0] * 20,
        "close": [100.0] * 20,
        "volume": [10.0] * 20,
    })
    result = evaluate_indicator_brain(frame)
    assert result["available"] is False
    assert result["reason"] == "insufficient_ohlcv_history"
