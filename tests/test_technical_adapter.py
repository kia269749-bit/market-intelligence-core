from mi_core.brains.contracts import MarketSnapshot
from mi_core.brains.technical_adapter import evaluate_technical_specialists


def test_all_default_technical_brains_report_missing_data_explicitly():
    rows = evaluate_technical_specialists(MarketSnapshot("BTC", 100_000, "1h"))
    assert {row.brain_id for row in rows} == {
        "technical.pandas_ta_classic.15m",
        "technical.pandas_ta_classic.1h",
        "technical.pandas_ta_classic.4h",
        "technical.pandas_ta_classic.1d",
    }
    assert all(row.available is False and row.direction == "NO_TRADE" for row in rows)
