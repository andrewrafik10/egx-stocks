"""Telegram summary for the V2 EGX research engine."""
from datetime import date

def _pct(x):
    return "—" if x is None else f"{x:+.1%}"

def _fv(x):
    return "—" if x is None else f"{x:.2f}"

def build_report(ranked, top_n=10):
    today = date.today().strftime("%d %b %Y")
    usable = [r for r in ranked if r.get("opportunity_score") is not None]
    high = sum(r["confidence"] == "High" for r in usable)
    med = sum(r["confidence"] == "Medium" for r in usable)
    low = sum(r["confidence"] == "Low" for r in usable)

    lines = [
        f"*EGX100 V2 Fundamental Research — {today}*",
        f"_{len(usable)} of {len(ranked)} stocks scored_",
        f"Confidence: 🟢 {high} High | 🟡 {med} Medium | 🔴 {low} Low",
        "",
        "*Top V2 Opportunities:*",
    ]

    for i, r in enumerate(usable[:top_n], 1):
        base_up = ((r["fair_value_base"] - r["price"]) / r["price"]
                   if r["fair_value_base"] and r["price"] else None)
        lines.append(
            f"{i}. *{r['ticker']}* — Score {r['opportunity_score']:.1f} | {_pct(base_up)} base upside\n"
            f"   {r['sector']} | Price {r['price']:.2f} | Base FV {_fv(r['fair_value_base'])}\n"
            f"   Range: {_fv(r['fair_value_bear'])}–{_fv(r['fair_value_bull'])} | "
            f"Dispersion {_pct(r['dispersion'])} | Quality "
            f"{r['quality_score'] if r['quality_score'] is not None else '—'}"
        )

    lines += [
        "",
        "_Quantitative research/screening only — not investment advice. "
        "High valuation dispersion means the methods disagree and warrants additional review._",
    ]

    full_text = "\n".join(lines)
    messages = []
    chunk = ""
    for line in full_text.split("\n"):
        if len(chunk) + len(line) + 1 > 4000:
            messages.append(chunk)
            chunk = line
        else:
            chunk = f"{chunk}\n{line}" if chunk else line
    if chunk:
        messages.append(chunk)
    return messages
