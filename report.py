"""
Formats the ranked list into a Telegram-friendly message (or messages).
"""

from datetime import date

METHOD_LABELS = {"pe": "P/E", "graham": "Graham", "dcf": "DCF", "comps": "Comps"}


def _fmt_pct(x):
    if x is None:
        return "—"
    return f"{x:+.1%}"


def build_report(ranked: list, top_n: int = 10) -> list:
    """Returns a list of message strings (split to respect Telegram's 4096-char limit)."""
    today = date.today().strftime("%d %b %Y")
    usable = [r for r in ranked if r["composite_upside"] is not None]

    high_conf = [r for r in usable if r.get("confidence") == "High"]
    medium_conf = [r for r in usable if r.get("confidence") == "Medium"]
    low_conf = [r for r in usable if r.get("confidence") == "Low"]

    lines = [
        f"*EGX Weekly Fundamental Report — {today}*",
        f"_{len(usable)} of {len(ranked)} stocks scored_",
        f"High Confidence: {len(high_conf)} | Medium: {len(medium_conf)} | Low: {len(low_conf)}",
        "",
        "*Top Opportunities (Highest Blended Upside):*",
    ]

    for rank, r in enumerate(usable[:top_n], 1):
        methods_str = " | ".join(
            f"{METHOD_LABELS[m]} {_fmt_pct(u)}" for m, u in r["upsides"].items()
        )

        conf = r.get("confidence", "Low")
        if conf == "High":
            conf_icon = "🟢"
        elif conf == "Medium":
            conf_icon = "🟡"
        else:
            conf_icon = "🔴"

        lines.append(
            f"{rank}. *{r['ticker']}* — {_fmt_pct(r['composite_upside'])}  {conf_icon} {conf}\n"
            f"   Price: {r['price']:.2f} | {methods_str}"
        )

    lines.append("")
    lines.append(
        "_Quantitative screening signal only — not investment advice. "
        "DCF uses sector-specific cost of equity. Graham is excluded for banks._"
    )

    full_text = "\n".join(lines)

    # Split into ≤4096 char chunks
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
