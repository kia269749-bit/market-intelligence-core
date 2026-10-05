from mi_core.cross_asset import CrossAssetSnapshot, cross_asset_regime
from mi_core.signal_gate import research_signal_summary

def test_risk_on_regime_supports_long_context():
    macro = cross_asset_regime(CrossAssetSnapshot(0.02,-0.01,0.01,0.02,-0.01))
    assert macro["regime"] == "RISK_ON_CRYPTO_SUPPORTIVE"
    summary = research_signal_summary(side="LONG", signal_score=.8, confidence=.8, gate_eligible=True,
        effective_confluence=.8, agreement=.9, regime_fit=1.0, fomo_supported=True, meme_supported=True)
    assert summary["regime_fit"] == 1.0
    assert summary["support_bonus"] == .08

def test_poor_regime_is_warned():
    summary = research_signal_summary(side="LONG", signal_score=.8, confidence=.8, gate_eligible=True,
        effective_confluence=.8, agreement=.9, regime_fit=.4)
    assert "POOR_MACRO_REGIME_FIT" in summary["warnings"]
