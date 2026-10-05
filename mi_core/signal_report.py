"""Research-only human-readable market decision summary."""
from __future__ import annotations
from typing import Mapping


def _bias_value(value) -> float:
    return {"BULLISH": 1.0, "BEARISH": -1.0, "LONG": 1.0, "SHORT": -1.0}.get(str(value).upper(), 0.0)


def build_signal_report(*, symbol: str, signal: Mapping, signal_summary: Mapping,
                        flow: Mapping, positioning: Mapping, microstructure: Mapping,
                        cross_exchange: Mapping, confluence: Mapping, crowding: Mapping,
                        fomo: Mapping | None = None, macro: Mapping | None = None,
                        meme: Mapping | None = None,
                        historical_evidence: Mapping | None = None) -> dict:
    """Aggregate intelligence layers and historical evidence into manual review."""
    direction = signal_summary.get("direction", "FLAT")
    confirmations = 0
    conflicts = 0
    layer_states = {}
    checks = (("flow", flow.get("bias")), ("positioning", positioning.get("bias")),
              ("microstructure", microstructure.get("bias")), ("cross_exchange", cross_exchange.get("bias")))
    target = 1.0 if direction == "LONG" else -1.0 if direction == "SHORT" else 0.0

    for name, bias in checks:
        value = _bias_value(bias)
        state = "NEUTRAL"
        if target and value:
            state = "CONFIRMS" if value == target else "CONFLICTS"
            confirmations += value == target
            conflicts += value != target
        layer_states[name] = state

    exchange_confirmed = bool(cross_exchange.get("confirmed"))
    if target:
        layer_states["cross_exchange_confirmation"] = "CONFIRMS" if exchange_confirmed else "NOT_CONFIRMED"

    reasons = []
    warnings = list(signal_summary.get("warnings", ()))
    if confirmations:
        reasons.append(f"{confirmations} intelligence layer(s) confirm direction")
    if conflicts:
        reasons.append(f"{conflicts} intelligence layer(s) conflict with direction")
    if crowding.get("level") in {"NORMAL", "ELEVATED", "EXTREME"}:
        reasons.append(f"crowding={crowding['level']}")
    if flow.get("smart_money_score", 0) * target > 0:
        reasons.append("smart money flow confirms direction")
    if historical_evidence:
        oos = historical_evidence.get("oos", {})
        pf = oos.get("profit_factor")
        if isinstance(pf, (int, float)) and pf >= 1.0 and oos.get("trades_count", 0) > 0:
            reasons.append("historical OOS evidence is positive")
        else:
            warnings.append("WEAK_HISTORICAL_OOS_EVIDENCE")
        anti = historical_evidence.get("anti_overfitting", {})
        if anti.get("score", 0.0) < 0.50:
            warnings.append("LOW_ANTI_OVERFITTING_SCORE")

    if fomo and fomo.get("event"):
        event = fomo["event"]
        if isinstance(event, Mapping) and event.get("is_fomo"):
            warnings.append("FOMO_EVENT")
    if target and exchange_confirmed:
        confirmations += 1

    conviction = float(signal_summary.get("conviction", 0.0))
    risk_level = ("HIGH" if crowding.get("cascade_risk") or crowding.get("level") == "EXTREME"
                  else "ELEVATED" if crowding.get("level") == "ELEVATED" or conflicts >= 2 else "LOW")
    decision = ("NO_SIGNAL" if direction == "FLAT"
                else "MANUAL_REVIEW_REQUIRED" if signal_summary.get("status") in {"STRONG", "WATCH"}
                else "FILTERED")
    confirmation_ratio = confirmations / max(1, confirmations + conflicts)
    return {
        "symbol": symbol, "direction": direction, "status": signal_summary.get("status", "NO_SIGNAL"),
        "conviction": round(conviction, 6), "conviction_pct": round(conviction * 100, 2),
        "confirmation_ratio": round(confirmation_ratio, 6), "risk_level": risk_level, "decision": decision,
        "confirmations": confirmations, "conflicts": conflicts, "layers": layer_states,
        "flow_bias": flow.get("bias", "NEUTRAL"), "smart_money_score": flow.get("smart_money_score", 0.0),
        "positioning_bias": positioning.get("bias", "NEUTRAL"), "microstructure_bias": microstructure.get("bias", "NEUTRAL"),
        "cross_exchange_confirmed": exchange_confirmed, "crowding_level": crowding.get("level", "NORMAL"),
        "crowding_score": crowding.get("score", 0.0), "cascade_risk": bool(crowding.get("cascade_risk", False)),
        "historical_evidence": historical_evidence,
        "fomo": fomo, "macro": macro, "meme": meme,
        "reasons": tuple(dict.fromkeys(reasons)), "warnings": tuple(dict.fromkeys(warnings)),
        "manual_review": True, "research_only": True, "live_orders": False,
    }


def render_signal_report(report: Mapping) -> str:
    """Render a deterministic, copy/paste-friendly manual signal summary."""
    def mark(state: str) -> str:
        return "YES" if state == "CONFIRMS" else "NO" if state in {"CONFLICTS", "NOT_CONFIRMED"} else "-"
    layers = report.get("layers", {})
    warnings, reasons = report.get("warnings", ()), report.get("reasons", ())
    history = report.get("historical_evidence") or {}
    oos, mc, anti = history.get("oos", {}), history.get("monte_carlo") or {}, history.get("anti_overfitting") or {}
    lines = [
        str(report.get("symbol", "UNKNOWN")), f"Direction: {report.get('direction', 'FLAT')}",
        f"Conviction: {float(report.get('conviction_pct', 0.0)):.2f}%", f"Status: {report.get('status', 'NO_SIGNAL')}",
        f"Risk: {report.get('risk_level', 'UNKNOWN')}", "",
        f"Flow: {report.get('flow_bias', 'NEUTRAL')} [{mark(layers.get('flow', 'NEUTRAL'))}]",
        f"Smart Money: {float(report.get('smart_money_score', 0.0)):.2f}",
        f"Positioning: {report.get('positioning_bias', 'NEUTRAL')} [{mark(layers.get('positioning', 'NEUTRAL'))}]",
        f"Microstructure: {report.get('microstructure_bias', 'NEUTRAL')} [{mark(layers.get('microstructure', 'NEUTRAL'))}]",
        f"Cross-Exchange: {report.get('cross_exchange_confirmed', False)} [{mark(layers.get('cross_exchange_confirmation', 'NEUTRAL'))}]",
        f"Crowding: {report.get('crowding_level', 'NORMAL')}", f"Cascade Risk: {report.get('cascade_risk', False)}", "",
        f"Confirmations: {report.get('confirmations', 0)}", f"Conflicts: {report.get('conflicts', 0)}",
        f"Confirmation Ratio: {float(report.get('confirmation_ratio', 0.0)):.2f}",
    ]
    if history:
        lines += ["", "Historical Evidence:",
                  f"OOS Return: {float(oos.get('return', 0.0)) * 100:.2f}%",
                  f"OOS Profit Factor: {oos.get('profit_factor', 'n/a')}",
                  f"OOS Trades: {oos.get('trades_count', 0)}",
                  f"Monte Carlo Loss Probability: {float(mc.get('probability_of_loss', 0.0)) * 100:.1f}%" if mc else "Monte Carlo: unavailable",
                  f"Anti-Overfitting Score: {float(anti.get('score', 0.0)):.2f}" if anti else "Anti-Overfitting: unavailable"]
    lines += ["", f"Decision: {report.get('decision', 'NO_SIGNAL')}", "Manual Review: YES", "Research Only: YES", "Live Orders: NO"]
    if reasons:
        lines.extend(["", "Reasons:"] + [f"- {reason}" for reason in reasons])
    if warnings:
        lines.extend(["", "Warnings:"] + [f"- {warning}" for warning in warnings])
    return "\n".join(lines)
