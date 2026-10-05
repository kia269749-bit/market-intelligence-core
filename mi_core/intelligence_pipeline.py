"""High-level, research-only market intelligence orchestration."""
from __future__ import annotations
from dataclasses import asdict
from typing import Mapping, Sequence
from .cross_asset import CrossAssetSnapshot, cross_asset_regime
from .features import order_imbalance
from .fomo_intelligence import analyze_fomo
from .fomo_historical import validate_fomo_evidence
from .intelligence import score_bar
from .macro_gate import macro_regime_fit
from .positioning import analyze_positioning
from .microstructure import cross_exchange_confirmation, microstructure_score
from .confluence import confluence_score
from .crowding import analyze_crowding
from .meme_candidate_scoring import score_meme_candidate
from .signal_gate import SignalQuality, signal_quality_gate, research_signal_summary
from .signal_report import build_signal_report

def _flow_report(bar)->dict:
    flow_imbalance=order_imbalance(bar.buy_volume,bar.sell_volume); whale_imbalance=order_imbalance(bar.whale_buy,bar.whale_sell)
    funding_pressure=-(bar.funding or 0)*10; sentiment=float(bar.sentiment)
    components={"order_flow":round(flow_imbalance,6),"whale_flow":round(whale_imbalance,6),"funding_pressure":round(funding_pressure,6),"sentiment":round(sentiment,6)}
    smart_money=max(-1,min(1,.55*whale_imbalance+.45*flow_imbalance)); composite=max(-1,min(1,.45*flow_imbalance+.35*whale_imbalance+.10*funding_pressure+.10*sentiment))
    return {"components":components,"smart_money_score":round(smart_money,6),"composite_flow_score":round(composite,6),
            "bias":"BULLISH" if composite>=.20 else "BEARISH" if composite<=-.20 else "NEUTRAL","diagnostic_only":True}

def analyze_market(bars:Sequence,*,volume_history:Sequence[float]|None=None,trader_metrics:Mapping[str,float]|None=None,
 macro:CrossAssetSnapshot|None=None,meme:Mapping[str,float]|None=None,entry_threshold:float=.60,historical_evidence:Mapping|None=None)->dict:
    if not bars: raise ValueError("bars must not be empty")
    bar,recent=bars[-1],list(bars[-21:-1]); signal=score_bar(bar,recent,entry_threshold=entry_threshold); flow=_flow_report(bar)
    positioning=analyze_positioning(getattr(bar,"derivatives",{}) or {}); crowding=analyze_crowding(getattr(bar,"derivatives",{}) or {})
    microstructure=microstructure_score(getattr(bar,"microstructure",{}) or {})
    exchange_confirmation=cross_exchange_confirmation(getattr(bar,"exchange_snapshots",()) or ())
    confluence=confluence_score(
      signal_score=signal.score if signal.side=="LONG" else -signal.score if signal.side=="SHORT" else 0,
      flow_score=flow["composite_flow_score"],positioning_score=positioning["positioning_score"],
      microstructure_score=microstructure["score"],exchange_score=exchange_confirmation["score"],
      exchange_quality=(exchange_confirmation["qualified_exchanges"]/exchange_confirmation["exchanges"] if exchange_confirmation["exchanges"] else 0.0))
    fomo=None; fomo_history=validate_fomo_evidence(historical_evidence)
    if volume_history is not None:
      fomo=asdict(analyze_fomo(symbol=bar.symbol,timestamp=bar.ts,volume_history=volume_history,current_volume=bar.volume,trader_metrics=trader_metrics,
        price_history=[x.price for x in bars[-len(volume_history):]] if volume_history else None,current_price=bar.price))
      fomo["historical_evidence"]=fomo_history
      if fomo_history["status"]=="WEAK": fomo["actionable_research_flag"]=False
    macro_report,macro_fit=None,.60
    if macro is not None and signal.side!="FLAT": macro_report=cross_asset_regime(macro); macro_fit=macro_regime_fit(signal.side,macro)
    fomo_score=fomo.get("event",{}).get("score",0) if isinstance(fomo,dict) and isinstance(fomo.get("event"),dict) else 0
    data_quality=1.0 if len(bars)>=30 else len(bars)/30; confidence=min(1,.70*signal.confidence+.30*max(signal.score,fomo_score))
    gate=signal_quality_gate(SignalQuality(score=signal.score,confidence=confidence,edge=signal.score-entry_threshold,data_quality=data_quality,regime_fit=macro_fit,decay=1.0))
    meme_report=None
    if meme is not None:
      meme_report=asdict(score_meme_candidate(meme.get("token",bar.symbol),liquidity_usd=float(meme["liquidity_usd"]),volume_24h_usd=float(meme["volume_24h_usd"]),
        holders=int(meme["holders"]),top_holder_pct=float(meme["top_holder_pct"]),buy_sell_ratio=float(meme["buy_sell_ratio"]),
        smart_money_score=float(meme["smart_money_score"]),fomo_score=float(meme["fomo_score"]),historical_evidence=historical_evidence))
    signal_summary=research_signal_summary(side=signal.side,signal_score=signal.score,confidence=confidence,gate_eligible=gate["eligible"],
      effective_confluence=confluence["effective_score"],agreement=confluence["agreement"],crowding_score=crowding["score"],
      cascade_risk=crowding["cascade_risk"],oi_funding_divergence=crowding["oi_funding_divergence"],regime_fit=macro_fit,
      fomo_supported=bool(fomo and fomo.get("historical_evidence",{}).get("supported")),meme_supported=bool(meme_report and meme_report.get("historical_evidence_status")=="SUPPORTED"))
    final_report=build_signal_report(symbol=bar.symbol,signal=signal.to_dict(),signal_summary=signal_summary,flow=flow,positioning=positioning,
      microstructure=microstructure,cross_exchange=exchange_confirmation,confluence=confluence,crowding=crowding,fomo=fomo,macro=macro_report,meme=meme_report,historical_evidence=historical_evidence)
    return {"timestamp":bar.ts,"symbol":bar.symbol,"price":bar.price,"flow":flow,"positioning":positioning,"crowding":crowding,"microstructure":microstructure,
      "cross_exchange":exchange_confirmation,"confluence":confluence,"signal":signal.to_dict(),"fomo":fomo,"macro":macro_report,"meme":meme_report,
      "signal_gate":gate,"signal_summary":signal_summary,"historical_evidence":historical_evidence,"fomo_historical_evidence":fomo_history,
      "final_report":final_report,"research_only":True,"live_orders":False}
