"""
Formats the ranked list into a Telegram-friendly message (or messages, since
Telegram caps a single message at 4096 characters).
"""

from datetime import date

METHOD_LABELS = {"pe": "P/E", "graham": "Graham", "dcf": "DCF", "comps": "Comps"}


def _fmt_pct(x):
    if x is None:
        return "—"
    return f"{x:+.1%}"


def build_report(ranked: list, top_n: int = 15) -> list:
    """Returns a list of message strings (split to respect Telegram's 4096-char limit)."""
    today = date.today().strftime("%d %b %Y")
    usable = [r for r in ranked if r["composite_upside"] is not None]
    unusable = [r for r in ranked if r["composite_upside"] is None]

    lines = [f"*EGX Weekly Fundamental Scan — {today}*",
             f"_{len(usable)} of {len(ranked)} stocks scored (composite of P/E, Graham, DCF, Comps)_",
             ""]

    lines.append("*Top opportunities (highest blended upside):*")
    for rank, r in enumerate(usable[:top_n], 1):
        methods_str = " ".join(
            f"{METHOD_LABELS[m]}:{_fmt_pct(u)}" for m, u in r["upsides"].items()
        )
        flag = " ⚠️ low coverage" if r["methods_used"] <= 1 else ""
        lines.append(
            f"{rank}. *{r['ticker']}* — {_fmt_pct(r['composite_upside'])} "
            f"(price {r['price']:.2f}){flag}\n   {methods_str}"
        )

    if unusable:
        tickers = ", ".join(r["ticker"] for r in unusable)
        lines.append("")
        lines.append(f"*Insufficient data to score ({len(unusable)}):* {tickers}")

    lines.append("")
    lines.append(
        "_Screening signal only, not investment advice. DCF/Graham unreliable for "
        "negative-FCF or bank names — see method flags above._"
    )

    full_text = "\n".join(lines)

    # split into <=4096 char chunks on line boundaries
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
