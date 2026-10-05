"""Persian human-readable Market Brain guidance."""
from __future__ import annotations

def _num(v,default=0.0):
    try: return float(v)
    except (TypeError,ValueError): return default

def build_action(market_rows,bias,confidence):
    rows=[r for r in market_rows if r.get("price") is not None]
    if not rows: return {"status":"WAIT","reason":"قیمت معتبر در داده بازار موجود نیست."}
    row=next((r for r in rows if str(r.get("symbol","")).upper() in ("BTCUSDT","BTC")),rows[0])
    price=_num(row.get("price"))
    if price<=0: return {"status":"WAIT","reason":"قیمت معتبر نیست."}
    if bias=="BULLISH" and _num(confidence)>=0.65:
        return {"status":"WATCH_BUY","symbol":row.get("symbol"),"price":price,"entry_low":price*0.997,"entry_high":price*1.001,"stop":price*0.992,"target1":price*1.012,"target2":price*1.025,"reason":"جهت بازار صعودی و اعتماد کافی است؛ ورود روی پولبک کم‌ریسک‌تر از تعقیب جهش است."}
    if bias=="BEARISH" and _num(confidence)>=0.65:
        return {"status":"WATCH_SELL","symbol":row.get("symbol"),"price":price,"exit_low":price*0.999,"exit_high":price*1.002,"invalid":price*1.008,"reason":"فشار نزولی و اعتماد کافی دیده می‌شود؛ خروج یا کاهش ریسک را بررسی کن."}
    return {"status":"WAIT","symbol":row.get("symbol"),"price":price,"reason":"شواهد هنوز برای ورود یا خروج با اعتماد کافی هم‌جهت نیستند."}

def render_persian(snapshot,project60=None):
    e=snapshot.get("evidence",{}); m=e.get("market",{}); f=e.get("fomo",{})
    bias=m.get("bias","NEUTRAL"); confidence=_num(m.get("confidence"),0)
    a=build_action(snapshot.get("market",{}).get("rows",[]),bias,confidence)
    lines=["🧠 گزارش هوش بازار","📊 وضعیت: {} | اعتماد: {:.0f}٪".format(bias,confidence*100),"🌐 منابع بازار: {}".format(m.get("sources",0)),"🧲 FOMO: {} کاندید | رصد والت: {}".format(f.get("candidates",0),"فعال" if f.get("wallet_level") else "فعلاً غیرفعال"),"","📌 راهنمای تحلیلی"]
    if a["status"]=="WATCH_BUY":
        lines += ["🟢 سناریو: بررسی ورود","💰 محدوده ورود: {:.2f} تا {:.2f}".format(a["entry_low"],a["entry_high"]),"🛑 حد بی‌اعتباری: {:.2f}".format(a["stop"]),"🎯 هدف ۱: {:.2f}".format(a["target1"]),"🎯 هدف ۲: {:.2f}".format(a["target2"]),"💡 "+a["reason"]]
    elif a["status"]=="WATCH_SELL":
        lines += ["🔴 سناریو: بررسی خروج/کاهش ریسک","💰 محدوده خروج: {:.2f} تا {:.2f}".format(a["exit_low"],a["exit_high"]),"⚠️ بی‌اعتباری هشدار: بالای {:.2f}".format(a["invalid"]),"💡 "+a["reason"]]
    else: lines += ["⚪ فعلاً صبر","💡 "+a["reason"]]
    lines += ["","⚠️ خروجی پژوهشی است؛ قیمت‌ها سطح‌های محاسباتی‌اند، نه تضمین معامله یا سود."]
    return "\n".join(lines)