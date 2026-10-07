# Predictive entry/exit timing engine
# Research-only scaffold. No live order execution.

def evaluate_entry_timing(confidence=0.0, expected_move_pct=0.0, current_move_pct=0.0, required_move_pct=0.0, agreement=0.0, quality_score=0.0, regime="UNKNOWN"):
    confidence=float(confidence); agreement=float(agreement); quality_score=float(quality_score)
    expected_move_pct=abs(float(expected_move_pct)); current_move_pct=abs(float(current_move_pct)); required_move_pct=max(0.0,float(required_move_pct))
    remaining=max(0.0, expected_move_pct-current_move_pct)
    extension=current_move_pct/max(expected_move_pct,1e-9)
    consumed_ratio=min(1.0, extension)
    if expected_move_pct<=0: state,reason="WAIT","no_remaining_expected_move"
    elif extension>=0.75: state,reason="LATE","most_of_modeled_move_already_consumed"
    elif confidence>=0.68 and agreement>=0.60 and quality_score>=0.90 and remaining>=required_move_pct and str(regime).upper() in ("TREND","MIXED"):
        state,reason="EARLY","meaningful_move_remains_with_multi_source_confirmation"
    elif remaining>0: state,reason="DEVELOPING","setup_developing_but_not_early_entry_grade"
    else: state,reason="WAIT","remaining_move_below_economic_requirement"
    return {"state":state,"reason":reason,"expected_move_pct":round(expected_move_pct,4),"current_move_pct":round(current_move_pct,4),"remaining_move_pct":round(remaining,4),"extension_ratio":round(extension,4),"consumed_ratio":round(consumed_ratio,4),"consumed_pct":round(consumed_ratio*100.0,2),"research_only":True,"live_orders":False}

def evaluate_exit_timing(position_open=True, profit_pct=0.0, momentum_score=0.0, leader_exit=False, orderbook_deterioration=False, tradeflow_deterioration=False, forecast_reversal=False, remaining_move_pct=0.0):
    if not position_open: return {"state":"NO_POSITION","reason":"no_position_context","research_only":True,"live_orders":False}
    profit_pct=float(profit_pct); momentum_score=max(-1.0,min(1.0,float(momentum_score))); remaining_move_pct=max(0.0,float(remaining_move_pct))
    warnings=sum([bool(leader_exit),bool(orderbook_deterioration),bool(tradeflow_deterioration),bool(forecast_reversal),momentum_score < -0.35])
    if warnings>=3 or (forecast_reversal and momentum_score < -0.35): state,reason="EXIT","multiple_exit_evidence_sources"
    elif warnings>=2: state,reason="TAKE_PROFIT","early_distribution_or_momentum_warning"
    elif warnings==1 and profit_pct>0: state,reason="TRAIL","first_exit_warning_while_profitable"
    elif profit_pct>0 and remaining_move_pct<=0: state,reason="TAKE_PROFIT","modeled_remaining_move_exhausted"
    else: state,reason="HOLD","exit_evidence_not_yet_strong"
    return {"state":state,"reason":reason,"profit_pct":round(profit_pct,4),"momentum_score":round(momentum_score,4),"warnings":warnings,"remaining_move_pct":round(remaining_move_pct,4),"research_only":True,"live_orders":False}
