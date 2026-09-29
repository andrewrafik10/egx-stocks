"""Telegram summary for the V3 EGX research engine."""
from datetime import date
def _pct(x): return "—" if x is None else f"{x:+.1%}"
def _fv(x): return "—" if x is None else f"{x:.2f}"
def build_report(ranked, top_n=10):
    usable=[r for r in ranked if r.get("opportunity_score") is not None]
    high=sum(r["confidence"]=="High" for r in usable); med=sum(r["confidence"]=="Medium" for r in usable); low=sum(r["confidence"]=="Low" for r in usable)
    lines=[f"*EGX100 V3 Fundamental Research — {date.today():%d %b %Y}*",f"_{len(usable)} of {len(ranked)} stocks scored_",f"Confidence: 🟢 {high} High | 🟡 {med} Medium | 🔴 {low} Low","","*Top V3 Research Signals:*"]
    for i,r in enumerate(usable[:top_n],1):
        up=((r["fair_value_base"]-r["price"])/r["price"] if r["fair_value_base"] and r["price"] else None)
        lines.append(f"{i}. *{r['ticker']}* — Score {r['opportunity_score']:.1f} | {_pct(up)} base upside\n   {r['sector']} | Price {r['price']:.2f} | Base FV {_fv(r['fair_value_base'])}\n   Methods: {', '.join(r['applicable_methods'])} | Coverage {r['valuation_coverage']:.0%}\n   Valuation {r['valuation_score'] if r['valuation_score'] is not None else '—'} | Quality {r['quality_score'] if r['quality_score'] is not None else '—'} | Confidence {r['confidence']}\n   Status: {r['research_status']}")
    lines += ["","_V3 is quantitative research/screening only — not investment advice._"]
    msgs=[]; chunk=""
    for line in lines:
        if len(chunk)+len(line)+1>4000: msgs.append(chunk); chunk=line
        else: chunk=f"{chunk}\n{line}" if chunk else line
    if chunk: msgs.append(chunk)
    return msgs
