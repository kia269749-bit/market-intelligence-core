"""Persian human-readable Market Brain guidance with a cost-aware profitability gate."""
from __future__ import annotations
from .usd10_filter import evaluate_usd10_setup

def _num(v, default=0.0):
    try: return float(v)
    except (TypeError, ValueError): return default

def build_action(market_rows, bias, confidence, risk_policy=None):
    rows=[r for r in market_rows if r.get("price") is not None]
    if not rows: return {"status":"WAIT","reason":"قیمت معتبر در داده بازار موجود نیست."}
    row=next((r for r in rows if str(r.get("symbol","")).upper() in ("BTCUSDT","BTC")),rows[0])
    price=_num(row.get("price"))
    if price<=0: return {"status":"WAIT","reason":"قیمت معتبر نیست."}
    policy=risk_policy or {}
    min_profit=_num(policy.get("min_net_profit_usd"),10.0)
    max_position=_num(policy.get("max_position_usd"),1000.0)
    max_risk=_num(policy.get("max_risk_usd"),15.0)
    if bias=="BULLISH" and _num(confidence)>=0.65:
        stop=price*0.992
        target1=price*1.012
        target2=price*1.025
        gate=evaluate_usd10_setup(price,stop,target2,"BULLISH",_num(confidence),min_net_profit_usd=min_profit,max_position_usd=max_position,max_risk_usd=max_risk)
        if not gate.approved:
            return {"status":"WAIT","symbol":row.get("symbol"),"price":price,"gate":gate,
                    "reason":"سیگنال جهت‌دار است اما بعد از کارمزد/اسپرد/اسلیپیج، مزیت خالص یا R/R کافی نیست."}
        return {"status":"WATCH_BUY","symbol":row.get("symbol"),"price":price,
                "entry_low":price*0.997,"entry_high":price*1.001,"stop":stop,
                "target1":target1,"target2":target2,"gate":gate,
                "reason":"شواهد ترکیبی صعودی و مزیت خالصِ هزینه‌محور از حداقل گیت عبور کرده است."}
    if bias=="BEARISH" and _num(confidence)>=0.65:
        stop=price*1.008
        target=price*0.975
        gate=evaluate_usd10_setup(price,stop,target,"BEARISH",_num(confidence),min_net_profit_usd=min_profit,max_position_usd=max_position,max_risk_usd=max_risk)
        if not gate.approved:
            return {"status":"WAIT","symbol":row.get("symbol"),"price":price,"gate":gate,
                    "reason":"فشار نزولی هست اما بعد از هزینه‌ها، مزیت خالص یا R/R کافی نیست."}
        return {"status":"WATCH_SELL","symbol":row.get("symbol"),"price":price,
                "exit_low":price*0.999,"exit_high":price*1.002,"invalid":stop,
                "target":target,"gate":gate,
                "reason":"فشار ترکیبی نزولی و مزیت خالصِ هزینه‌محور از حداقل گیت عبور کرده است."}
    return {"status":"WAIT","symbol":row.get("symbol"),"price":price,
            "reason":"شواهد هنوز برای ورود یا خروج با اعتماد کافی هم‌جهت نیستند."}

def _project60_lines(project60):
    if not project60 or not project60.get("available"):
        return ["🏛️ Project 60: داده زنده در دسترس نیست."]
    lines=["🏛️ Project 60: {} | اعتماد: {:.0f}٪".format(project60.get("bias","UNKNOWN"),_num(project60.get("confidence"))*100)]
    assets=project60.get("assets") or {}
    for symbol in ("BTC","ETH"):
        a=assets.get(symbol)
        if not a or not a.get("available"): continue
        lines.append("  {}: {} | OB {:+.1f}% | Flow {:+.1f}% | OI {} | Funding {}".format(
            symbol,a.get("direction","UNKNOWN"),_num(a.get("orderbook_imbalance_pct")),
            _num(a.get("trade_imbalance_pct")),a.get("open_interest","N/A"),a.get("funding","N/A")))
        evidence=a.get("evidence") or []
        if evidence: lines.append("     شواهد: "+ "، ".join(evidence))
    return lines

def render_persian(snapshot, project60=None):
    e=snapshot.get("evidence",{}); m=e.get("market",{}); combined=e.get("combined",{})
    f=e.get("fomo",{}); lf=e.get("fomo_leader_follower",{})
    bias=str(combined.get("bias",m.get("bias","NEUTRAL"))).upper()
    confidence=_num(combined.get("confidence",m.get("confidence")),0)
    a=build_action(snapshot.get("market",{}).get("rows",[]),bias,confidence,snapshot.get("risk_policy"))
    lines=["🧠 گزارش هوش بازار",
           "📊 تصمیم ترکیبی: {} | اعتماد: {:.0f}٪".format(bias,confidence*100),
           "🌐 منابع بازار: {}".format(m.get("sources",0))]
    lines+=_project60_lines(project60 or snapshot.get("project60"))
    lines+=["🧭 Leader→Follower: {} رویداد تأییدشده".format(lf.get("confirmed") and len(lf.get("events",[])) or 0),
            "🧲 FOMO: {} کاندید | رصد والت: {}".format(f.get("candidates",0),"فعال" if f.get("wallet_level") else "فعلاً غیرفعال"),
            "","📌 راهنمای تحلیلی"]
    for i,row in enumerate(f.get("top",[])[:3],1):
        lines.append("  FOMO#{} {} | score={} | vol={:,.0f} | 24h={:+.2f}%".format(
            i,row.get("token","?"),row.get("fomo_score","?"),_num(row.get("volume_24h_usd")),
            _num(row.get("price_change_24h_pct"))))
    gate=a.get("gate")
    if a["status"]=="WATCH_BUY":
        lines += ["🟢 سناریو: بررسی ورود",
                  "💰 محدوده ورود: {:.2f} تا {:.2f}".format(a["entry_low"],a["entry_high"]),
                  "🛑 حد بی‌اعتباری: {:.2f}".format(a["stop"]),
                  "🎯 هدف ۱: {:.2f}".format(a["target1"]),
                  "🎯 هدف ۲: {:.2f}".format(a["target2"]),
                  "🧮 گیت $10: PASS | R/R خالص {:.2f} | هزینه {:.2f}%".format(gate.gate.net_rr,gate.gate.round_trip_cost_pct),
                  "💡 "+a["reason"]]
    elif a["status"]=="WATCH_SELL":
        lines += ["🔴 سناریو: بررسی خروج/کاهش ریسک",
                  "💰 محدوده خروج: {:.2f} تا {:.2f}".format(a["exit_low"],a["exit_high"]),
                  "🛑 حد بی‌اعتباری: {:.2f}".format(a["invalid"]),
                  "🎯 هدف: {:.2f}".format(a["target"]),
                  "🧮 گیت سوددهی: PASS | R/R خالص {:.2f} | هزینه مدل {:.2f}%".format(gate.net_rr,gate.round_trip_cost_pct),
                  "💡 "+a["reason"]]
    else:
        if gate:
            lines.append("🧮 گیت سوددهی: FAIL | {} | R/R خالص {:.2f}".format(gate.reason,gate.gate.net_rr))
        lines += ["⚪ فعلاً صبر","💡 "+a["reason"]]
    if gate and a["status"] in ("WATCH_BUY","WATCH_SELL"):
        lines.insert(-1, "📦 حجم مدل‌شده: ${:,.2f} | سود خالص مدل‌شده: ${:.2f} | زیان مدل‌شده: ${:.2f}".format(gate.position_usd,gate.modeled_net_profit_usd,gate.modeled_loss_usd))
    elif gate:
        lines.insert(-1, "📦 حجم لازم برای حداقل سود: ${:,.2f} | زیان مدل‌شده: ${:.2f}".format(gate.required_position_usd,gate.modeled_loss_usd))
    lines += ["","⚠️ خروجی پژوهشی است؛ گیت $10 یک فیلتر طراحی است و سود واقعی را تضمین نمی‌کند."]
    return "\n".join(lines)
