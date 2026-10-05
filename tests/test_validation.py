from mi_core.validation import validate_oos_robustness

def test_oos_monte_carlo_validation_is_research_only():
    report = {
        "oos_return_total": 0.20,
        "oos_positive_rate": 0.75,
        "research_only": True,
        "live_orders": False,
    }
    result = validate_oos_robustness(
        report, [0.02, 0.03, 0.01, -0.005, 0.025], train_return=0.25,
        simulations=100, seed=7,
    )
    assert result["research_only"] is True
    assert result["live_orders"] is False
    assert result["monte_carlo"]["simulations"] == 100
    assert 0 <= result["anti_overfitting"]["score"] <= 1
