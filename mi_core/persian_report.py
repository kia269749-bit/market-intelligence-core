"""Persian human-readable Market Brain guidance."""
from __future__ import annotations


def _num(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def build_action(market_rows, bias, confidence):
    rows = [r for r in market_rows if r.get("price") is not None]
    if not rows:
        return {"status": "WAIT", "reason": "قیمت معتبر در داده بازار موجود نیست."}
    row = next(
        (r for r in rows if str(r.get("symbol", "")).upper() in ("BTCUSDT", "BTC")),
        rows[0],
    )
    price = _num(row.get("price"))
    if price <= 0:
        return {"status": "WAIT", "reason": "قیمت معتبر نیست."}
    if bias == "BULLISH" and _num(confidence) >= 0.65:
        return {
            "status": "WATCH_BUY",
            "symbol": row.get("symbol"),
            "price": price,
            "entry_low": price * 0.997,
            "entry_high": price * 1.001,
            "stop": price * 0.992,
            "target1": price * 1.012,
            "target2": price * 1.025,
            "reason": "شواهد ترکیبی صعودی و اعتماد کافی است؛ ورود روی پولبک کم‌ریسک‌تر از تعقیب جهش است.",
        }
    if bias == "BEARISH" and _num(confidence) >= 0.65:
        return {
            "status": "WATCH_SELL",
            "symbol": row.get("symbol"),
            "price": price,
            "exit_low": price * 0.999,
            "exit_high": price * 1.002,
            "invalid": price * 1.008,
            "reason": "فشار ترکیبی نزولی و اعتماد کافی دیده می‌شود؛ خروج یا کاهش ریسک را بررسی کن.",
        }
    return {
        "status": "WAIT",
        "symbol": row.get("symbol"),
        "price": price,
        "reason": "شواهد هنوز برای ورود یا خروج با اعتماد کافی هم‌جهت نیستند.",
    }


def _project60_lines(project60):
    if not project60 or not project60.get("available"):
        return ["🏛️ Project 60: داده زنده در دسترس نیست."]
    lines = [
        "🏛️ Project 60: {} | اعتماد: {:.0f}٪".format(
            project60.get("bias", "UNKNOWN"),
            _num(project60.get("confidence")) * 100,
        )
    ]
    assets = project60.get("assets") or {}
    for symbol in ("BTC", "ETH"):
        a = assets.get(symbol)
        if not a or not a.get("available"):
            continue
        lines.append(
            "  {}: {} | OB {:+.1f}% | Flow {:+.1f}% | OI {} | Funding {}".format(
                symbol,
                a.get("direction", "UNKNOWN"),
                _num(a.get("orderbook_imbalance_pct")),
                _num(a.get("trade_imbalance_pct")),
                a.get("open_interest", "N/A"),
                a.get("funding", "N/A"),
            )
        )
        evidence = a.get("evidence") or []
        if evidence:
            lines.append("     شواهد: " + "، ".join(evidence))
    return lines


def render_persian(snapshot, project60=None):
    e = snapshot.get("evidence", {})
    m = e.get("market", {})
    combined = e.get("combined", {})
    f = e.get("fomo", {})
    lf = e.get("fomo_leader_follower", {})
    bias = str(combined.get("bias", m.get("bias", "NEUTRAL"))).upper()
    confidence = _num(combined.get("confidence", m.get("confidence")), 0)
    a = build_action(snapshot.get("market", {}).get("rows", []), bias, confidence)

    lines = [
        "🧠 گزارش هوش بازار",
        "📊 تصمیم ترکیبی: {} | اعتماد: {:.0f}٪".format(bias, confidence * 100),
        "🌐 منابع بازار: {}".format(m.get("sources", 0)),
    ]
    lines += _project60_lines(project60 or snapshot.get("project60"))
    lines += [
        "🧭 Leader→Follower: {} رویداد تأییدشده".format(lf.get("confirmed") and len(lf.get("events", [])) or 0),
        "🧲 FOMO: {} کاندید | رصد والت: {}".format(
            f.get("candidates", 0),
            "فعال" if f.get("wallet_level") else "فعلاً غیرفعال",
        ),
        "",
        "📌 راهنمای تحلیلی",
    ]

    for i, row in enumerate(f.get("top", [])[:3], 1):
        lines.append(
            "  FOMO#{} {} | score={} | vol={:,.0f} | 24h={:+.2f}%".format(
                i,
                row.get("token", "?"),
                row.get("fomo_score", "?"),
                _num(row.get("volume_24h_usd")),
                _num(row.get("price_change_24h_pct")),
            )
        )

    if a["status"] == "WATCH_BUY":
        lines += [
            "🟢 سناریو: بررسی ورود",
            "💰 محدوده ورود: {:.2f} تا {:.2f}".format(a["entry_low"], a["entry_high"]),
            "🛑 حد بی‌اعتباری: {:.2f}".format(a["stop"]),
            "🎯 هدف ۱: {:.2f}".format(a["target1"]),
            "🎯 هدف ۲: {:.2f}".format(a["target2"]),
            "💡 " + a["reason"],
        ]
    elif a["status"] == "WATCH_SELL":
        lines += [
            "🔴 سناریو: بررسی خروج/کاهش ریسک",
            "💰 محدوده خروج: {:.2f} تا {:.2f}".format(a["exit_low"], a["exit_high"]),
            "⚠️ بی‌اعتباری هشدار: بالای {:.2f}".format(a["invalid"]),
            "💡 " + a["reason"],
        ]
    else:
        lines += ["⚪ فعلاً صبر", "💡 " + a["reason"]]

    lines += [
        "",
        "⚠️ خروجی پژوهشی است؛ قیمت‌ها سطح‌های محاسباتی‌اند، نه تضمین معامله یا سود.",
    ]
    return "\n".join(lines)
