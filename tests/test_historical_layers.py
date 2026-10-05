from mi_core.fomo_historical import validate_fomo_evidence
from mi_core.meme_candidate_scoring import score_meme_candidate

def _evidence():
    return {"oos": {"profit_factor": 1.5, "trades_count": 20},
            "anti_overfitting": {"score": 0.8}}

def test_fomo_historical_evidence_supports_only_strong_history():
    result = validate_fomo_evidence(_evidence())
    assert result["supported"] is True
    assert result["status"] == "SUPPORTED"
    assert result["diagnostic_only"] is True

def test_meme_quality_uses_historical_evidence():
    result = score_meme_candidate("TEST", liquidity_usd=2_000_000, volume_24h_usd=10_000_000,
        holders=20_000, top_holder_pct=10, buy_sell_ratio=2, smart_money_score=1,
        fomo_score=1, historical_evidence=_evidence())
    assert result.historical_evidence_status == "SUPPORTED"
    assert result.historical_evidence_score > 0
    assert result.quality_score > 0
