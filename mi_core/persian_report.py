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

def _validated_action(snapshot):
    """Build a Persian report action only from the live brain's validated evidence."""
    e=snapshot.get("evidence",{}) or {}
    combined=e.get("combined",{}) or {}
    economics=snapshot.get("capital_economics") or e.get("capital_economics") or {}
    alignment=e.get("forecast_alignment") or {}
    no_trade=e.get("no_trade") or {}
    timing=e.get("timing") or {}
    forecast=e.get("forecast") or {}
    bias=str(combined.get("bias","NEUTRAL")).upper()
    reasons=no_trade.get("reasons") or []

    if no_trade.get("blocked"):
        return {"status":"WAIT","reason":"شرط ایمنی بازار فعال است: "+", ".join(reasons)}
    if not combined.get("actionable"):
        return {"status":"WAIT","reason":"مغز ترکیبی هنوز جهت/کیفیت کافی برای سیگنال تأییدشده ندارد."}
    if not economics.get("available") or not economics.get("approved"):
        return {"status":"WAIT","reason":"گیت اقتصادی عبور نکرده: "+str(economics.get("reason","economic_edge_unproven"))}
    if not alignment.get("approved"):
        return {"status":"WAIT","reason":"گیت جهت و اعتبارسنجی عبور نکرده: "+str(alignment.get("reason","forecast_not_validated"))}
    if timing.get("state") in ("LATE","WAIT"):
        return {"status":"WAIT","reason":"زمان ورود مناسب نیست: "+str(timing.get("reason",timing.get("state")))}

    selected=forecast.get("selected") if isinstance(forecast,dict) else {}
    selected=selected if isinstance(selected,dict) else {}
    direction=str(alignment.get("direction") or bias).upper()
    entry=_num(forecast.get("price") or forecast.get("current_price") or
                selected.get("current_price") or selected.get("price"))
    if entry<=0:
        asset=str(forecast.get("asset") or selected.get("asset") or "BTC").upper()
        for row in (snapshot.get("market",{}) or {}).get("rows",[]):
            symbol=str(row.get("symbol","")).upper().replace("-","").replace("/","")
            if symbol in (asset,asset+"USDT",asset+"USDC",asset+"USD") and _num(row.get("price"))>0:
                entry=_num(row.get("price"))
                break
    move=_num(economics.get("expected_move_pct"),_num(selected.get("expected_move_pct")))
    if entry<=0 or move<=0 or direction not in ("BULLISH","BEARISH"):
        return {"status":"WAIT","reason":"قیمت مرجع یا حرکت مورد انتظار معتبر نیست."}

    from .shadow_risk import build_risk_levels
    risk=build_risk_levels(entry,direction,move)
    target1=entry+(risk["target"]-entry)*0.5
    status="WATCH_BUY" if direction=="BULLISH" else "WATCH_SELL"
    execution_ready=bool(e.get("execution_ready"))
    if execution_ready:
        reason="گیت‌های جهت، اقتصاد، اعتبارسنجی و زمان‌بندی هم‌زمان عبور کرده‌اند؛ فقط پژوهشی/کاغذی."
    else:
        reason="نامزد جهت‌دار و اقتصادی است، اما زمان‌بندی هنوز برای ورود آماده نیست."
    return {
        "status":status,"symbol":forecast.get("asset") or selected.get("asset") or "BTC",
        "price":entry,"entry":entry,"stop":risk["stop"],"target1":target1,"target":risk["target"],
        "risk_reward":risk["risk_reward"],"expected_move_pct":move,
        "target_hit_probability":_num(selected.get("target_hit_probability")),
        "modeled_profit_usd":_num(economics.get("modeled_profit_usd")),
        "round_trip_cost_pct":_num(economics.get("round_trip_cost_pct")),
        "required_move_pct":_num(economics.get("required_move_pct")),
        "execution_ready":execution_ready,"timing_state":timing.get("state","UNKNOWN"),
        "reason":reason,
    }


def render_persian(snapshot, project60=None):
    e=snapshot.get("evidence",{}); m=e.get("market",{}); combined=e.get("combined",{})
    f=e.get("fomo",{}); lf=e.get("fomo_leader_follower",{})
    bias=str(combined.get("bias",m.get("bias","NEUTRAL"))).upper()
    confidence=_num(combined.get("confidence",m.get("confidence")),0)
    a=_validated_action(snapshot)
    quality=(snapshot.get("market",{}).get("data_quality") or e.get("data_quality") or {})
    qstatus=str(quality.get("status","UNKNOWN")).upper()
    qemoji={"HEALTHY":"🟢","DEGRADED":"🟡","UNSAFE":"🔴"}.get(qstatus,"⚪")
    lines=["🧠 گزارش هوش بازار",
           "{} سلامت داده: {} | منابع موفق: {}/{}".format(qemoji,
               {"HEALTHY":"سالم","DEGRADED":"کاهش‌یافته","UNSAFE":"ناامن"}.get(qstatus,qstatus),
               quality.get("successful_sources",0),quality.get("expected_sources",0)),
           "📊 تصمیم ترکیبی: {} | امتیاز اعتماد: {:.0f}٪".format(bias,confidence*100),
           "🌐 منابع بازار: {}".format(m.get("sources",0))]
    if qstatus=="UNSAFE":
        lines += ["⛔ داده ناامن است؛ ورود جدید تأیید نمی‌شود."]
    elif qstatus=="DEGRADED":
        lines += ["⚠️ داده ناقص است؛ فقط رصد و نامزدهای پژوهشی."]
    lines+=_project60_lines(project60 or snapshot.get("project60"))

    mtf=e.get("multi_timeframe") or {}
    if mtf.get("available"):
        lines.append("🕰️ چندبازه‌ای: {} | توافق {:.0f}٪ | امتیاز {:.2f}".format(
            mtf.get("bias","UNKNOWN"),_num(mtf.get("agreement"))*100,_num(mtf.get("score"))))
        for interval in ("5m","1h","4h"):
            row=(mtf.get("timeframes") or {}).get(interval) or {}
            if row.get("available"):
                lines.append("  {}: {} | RSI {:.1f} | ATR {:.3f}٪ | حمایت {} | مقاومت {} | شکست {} | کندل {}".format(
                    interval,row.get("direction","UNKNOWN"),_num(row.get("rsi14")),
                    _num(row.get("atr14_pct")),row.get("support50","?"),row.get("resistance50","?"),
                    row.get("breakout","?"),row.get("candle_pattern","?")))
        if mtf.get("structural_target_reference") is not None:
            lines.append("📍 مرجع ساختاری هدف: {}".format(mtf.get("structural_target_reference")))
    else:
        lines.append("🕰️ چندبازه‌ای OHLC: در این چرخه داده معتبر کافی نبود.")

    fc=e.get("forecast") or {}
    alignment=e.get("forecast_alignment") or {}
    timing=e.get("timing") or {}
    if fc.get("available"):
        selected=fc.get("selected") or {}
        lines.append("🔮 پیش‌بینی: {} | حرکت تخمینی {:+.3f}٪ | احتمال برخورد هدف {:.0f}٪ | افق {} کندل".format(
            alignment.get("direction","UNKNOWN"),_num(selected.get("expected_return_pct",
            selected.get("expected_move_pct"))),_num(selected.get("target_hit_probability"))*100,
            selected.get("horizon","?")))
        lines.append("🧪 گیت پیش‌بینی: {} | {}".format(alignment.get("state","UNKNOWN"),alignment.get("reason","")))
        adaptive=fc.get("adaptive_validation") or {}
        if adaptive.get("available"):
            oos=adaptive.get("walk_forward_oos") or {}
            lines.append("🧠 انتخاب‌گر پویا: {} | مدل {} | معاملات OOS {} | سود خالص تجمعی {:.3f}٪ | PF {:.2f}".format(
                adaptive.get("status","UNKNOWN"),adaptive.get("selected_strategy","NONE"),
                oos.get("trades",0),_num(oos.get("net_profit_pct")),_num(oos.get("profit_factor"))))
    if timing:
        lines.append("⏱️ زمان‌بندی: {} | {} | حرکت باقی‌مانده {:.3f}٪".format(
            timing.get("state","UNKNOWN"),timing.get("reason",""),_num(timing.get("remaining_move_pct"))))

    lines += ["🧭 Leader→Follower: {} رویداد تأییدشده".format(lf.get("confirmed") and len(lf.get("events",[])) or 0),
              "🧲 FOMO: {} کاندید | رصد والت: {}".format(f.get("candidates",0),"فعال" if f.get("wallet_level") else "فعلاً غیرفعال"),
              "","📌 نتیجه‌ی عملیاتی"]

    for i,row in enumerate(f.get("top",[])[:3],1):
        lines.append("  FOMO#{} {} | score={} | vol={:,.0f} | 24h={:+.2f}%".format(
            i,row.get("token","?"),row.get("fomo_score","?"),_num(row.get("volume_24h_usd")),
            _num(row.get("price_change_24h_pct"))))

    if a["status"]=="WATCH_BUY":
        label="🟢 نامزد خرید، آماده‌ی ورود پژوهشی" if a["execution_ready"] else "🟡 نامزد خرید، هنوز ورود تأیید نشده"
        lines += [label,
                  "💰 قیمت مرجع: {:.4f}".format(a["entry"]),
                  "🛑 حد ضرر مدل: {:.4f}".format(a["stop"]),
                  "🎯 هدف میانی: {:.4f}".format(a["target1"]),
                  "🎯 هدف مدل: {:.4f}".format(a["target"]),
                  "📈 حرکت مورد انتظار: {:.3f}٪ | احتمال تاریخی برخورد هدف: {:.0f}٪".format(
                      a["expected_move_pct"],a["target_hit_probability"]*100),
                  "🧮 سود خالص مدل‌شده: USD {:.2f} | هزینه رفت‌وبرگشت: {:.3f}٪ | R/R {:.2f}".format(
                      a["modeled_profit_usd"],a["round_trip_cost_pct"],a["risk_reward"]),
                  "💡 "+a["reason"]]
    elif a["status"]=="WATCH_SELL":
        label="🔴 نامزد فروش/شورت، آماده‌ی ورود پژوهشی" if a["execution_ready"] else "🟡 نامزد نزولی، هنوز ورود تأیید نشده"
        lines += [label,
                  "💰 قیمت مرجع: {:.4f}".format(a["entry"]),
                  "🛑 حد ضرر مدل: {:.4f}".format(a["stop"]),
                  "🎯 هدف میانی: {:.4f}".format(a["target1"]),
                  "🎯 هدف مدل: {:.4f}".format(a["target"]),
                  "📉 حرکت مورد انتظار: {:.3f}٪ | احتمال تاریخی برخورد هدف: {:.0f}٪".format(
                      a["expected_move_pct"],a["target_hit_probability"]*100),
                  "🧮 سود خالص مدل‌شده: USD {:.2f} | هزینه رفت‌وبرگشت: {:.3f}٪ | R/R {:.2f}".format(
                      a["modeled_profit_usd"],a["round_trip_cost_pct"],a["risk_reward"]),
                  "💡 "+a["reason"]]
    else:
        lines += ["⚪ فعلاً ورود تأیید نمی‌شود",
                  "💡 "+a.get("reason","شواهد کافی برای ورود وجود ندارد.")]

    lines += ["","⚠️ پژوهشی/کاغذی است؛ هیچ سفارش واقعی ارسال نمی‌شود. مدل فقط وقتی ورود را آماده می‌داند که جهت، اقتصاد، اعتبارسنجی خارج از نمونه و زمان‌بندی هم‌زمان تأیید شوند."]
    return "\n".join(lines)
