"""Lightweight research-only performance metrics for the shadow journal."""
from __future__ import annotations
import json
from pathlib import Path

def load_resolved(path: str) -> list[dict]:
    p=Path(path)
    if not p.exists(): return []
    try: lines=p.read_text(encoding="utf-8").splitlines()
    except OSError: return []
    rows=[]
    for line in lines:
        try: row=json.loads(line)
        except json.JSONDecodeError: continue
        if row.get("status") in ("TARGET","STOP","EXPIRED"): rows.append(row)
    return rows

def summarize_performance(path: str) -> dict:
    """Summarize realized shadow performance without placing orders."""
    rows=load_resolved(path)
    profits=[float(r.get("net_profit_usd",0.0) or 0.0) for r in rows]
    outcome_rows=[r for r in rows if r.get("status") in ("TARGET","STOP")]
    wins=sum(r.get("status")=="TARGET" for r in outcome_rows)
    losses=sum(r.get("status")=="STOP" for r in outcome_rows)
    n=len(outcome_rows)
    closed=len(rows)
    expired=sum(r.get("status")=="EXPIRED" for r in rows)
    outcome_profits=[
        float(r.get("net_profit_usd",0.0) or 0.0)
        for r in outcome_rows
    ]
    gross_profit=sum(x for x in profits if x>0)
    gross_loss=abs(sum(x for x in profits if x<0))
    equity=peak=drawdown=0.0
    for pnl in profits:
        equity += pnl
        peak=max(peak,equity)
        drawdown=max(drawdown,peak-equity)
    hit4=sum(x>=4.0 for x in profits)
    hit10=sum(x>=10.0 for x in profits)
    return {
        "resolved":n,"closed":closed,"expired":expired,"wins":wins,"losses":losses,
        "win_rate":round(wins/n,4) if n else 0.0,
        "net_profit_usd":round(sum(profits),4),
        "average_net_profit_usd":round(sum(profits)/closed,4) if closed else 0.0,
        "expectancy_usd":round(sum(outcome_profits)/n,4) if n else 0.0,
        "profit_factor":round(gross_profit/gross_loss,4) if gross_loss else None,
        "max_drawdown_usd":round(drawdown,4),
        "profit_ge_4_usd":hit4,"profit_ge_10_usd":hit10,
        "hit_rate_ge_4_usd":round(hit4/closed,4) if closed else 0.0,
        "hit_rate_ge_10_usd":round(hit10/closed,4) if closed else 0.0,
        "research_only":True,"live_orders":False,
    }

def format_performance_line(metrics: dict) -> str:
    """Render a compact human-readable shadow performance line."""
    return (
        "Shadow: "
        f'{int(metrics.get("resolved",0))} resolved | '
        + (
            f'{int(metrics.get("expired",0))} expired | '
            if int(metrics.get("expired",0)) > 0 else ''
        )
        + f'Win {float(metrics.get("win_rate",0.0))*100:.0f}% | '
        f'Net ${float(metrics.get("net_profit_usd",0.0)):+.2f} | '
        f'Expectancy ${float(metrics.get("expectancy_usd",0.0)):+.2f} | '
        f'DD ${float(metrics.get("max_drawdown_usd",0.0)):.2f} | '
        f'≥$4: {int(metrics.get("profit_ge_4_usd",0))} | '
        f'≥$10: {int(metrics.get("profit_ge_10_usd",0))}'
    )
