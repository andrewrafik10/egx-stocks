"""Concise Telegram summary for the V3.1 EGX research screen."""
from datetime import date

def _pct(x):
    return "—" if x is None else f"{x:+.1%}"

def _fv(x):
    return "—" if x is None else f"{x:.2f}"

def _dq(r):
    return r.get("data_quality_score") or 0

def _is_candidate(r):
    up=((r.get("fair_value_base")-r.get("price"))/r.get("price")
        if r.get("fair_value_base") is not None and r.get("price") not in (None,0) else None)
    return (r.get("opportunity_score") is not None and up is not None and up>0
            and _dq(r)>=65 and r.get("confidence") in ("High","Medium")
            and r.get("research_signal") not in ("Data Limited","Deep Research Required"))

def build_report(ranked, top_n=10):
    usable=[r for r in ranked if r.get("opportunity_score") is not None]
    candidates=sorted((r for r in ranked if _is_candidate(r)),
                      key=lambda r:(r.get("opportunity_score") or 0,_dq(r)),reverse=True)[:top_n]
    high=sum(r.get("confidence")=="High" for r in usable)
    med=sum(r.get("confidence")=="Medium" for r in usable)
    low=sum(r.get("confidence")=="Low" for r in usable)
    lines=[
      f"*EGX100 V3.1 Fundamental Research — {date.today():%d %b %Y}*",
      f"_{len(usable)} of {len(ranked)} stocks scored_",
      f"Confidence: 🟢 {high} High | 🟡 {med} Medium | 🔴 {low} Low",
      f"Shortlist: {len(candidates)} passed positive-upside, data-quality and confidence filters.",
      "", "*Qualified Research Opportunities:*"
    ]
    if not candidates:
        lines.append("No stocks currently pass all shortlist filters. This is intentional; the model does not force recommendations.")
    for i,r in enumerate(candidates,1):
        up=((r["fair_value_base"]-r["price"])/r["price"] if r.get("fair_value_base") is not None and r.get("price") else None)
        lines.append(
          f"{i}. *{r['ticker']}* — Score {r['opportunity_score']:.1f} | {_pct(up)} upside\n"
          f"   {r.get('sector','—')} | Price {r['price']:.2f} | V3 FV {_fv(r.get('fair_value_base'))}\n"
          f"   Data Quality {_dq(r):.1f}/100 | Confidence {r.get('confidence','—')} | Coverage {r.get('valuation_coverage',0):.0%}"
        )
    lines += ["","_V3.1 is a quantitative research screen, not investment advice. Check the workbook's Risk & Quality sheet before relying on any signal._"]
    msgs=[]; chunk=""
    for line in lines:
        if len(chunk)+len(line)+1>4000:
            msgs.append(chunk); chunk=line
        else:
            chunk=f"{chunk}\n{line}" if chunk else line
    if chunk: msgs.append(chunk)
    return msgs
