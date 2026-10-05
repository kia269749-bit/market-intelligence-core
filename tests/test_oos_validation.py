from mi_core.oos_validation import evaluate_oos


def test_evaluate_oos_keeps_test_chronological():
    items = list(range(12))
    timestamps = list(range(12))

    def evaluator(train, test):
        return {"return": (test[-1] - test[0]) / 100.0, "trades_count": len(test)}

    result = evaluate_oos(items, timestamps, evaluator, train_size=6, test_size=2)
    assert result["research_only"] is True
    assert result["live_orders"] is False
    assert result["fold_count"] == 3
    assert result["oos_positive_rate"] == 1.0
    assert result["folds"][0]["fold"]["test_start"] == 6
    assert result["folds"][0]["fold"]["test_end"] == 8
