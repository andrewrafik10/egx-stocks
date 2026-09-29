"""Single-workbook V3 research report."""
from pathlib import Path
from datetime import date
import csv
from openpyxl import Workbook
from openpyxl.styles import Font,PatternFill,Alignment,Border,Side
from openpyxl.utils import get_column_letter
from openpyxl.formatting.rule import ColorScaleRule
from backtest_v3 import evaluate

NAVY="1F4E78"; WHITE="FFFFFF"; GREEN="C6EFCE"; YELLOW="FFEB9C"; RED="FFC7CE"
BORDER=Border(*(Side(style="thin",color="D9D9D9"),)*4)
def header(ws,row,headers):
    for i,h in enumerate(headers,1):
        c=ws.cell(row,i,h); c.fill=PatternFill("solid",fgColor=NAVY); c.font=Font(color=WHITE,bold=True); c.alignment=Alignment(horizontal="center",wrap_text=True); c.border=BORDER

def build_excel_v3(rows,output_path,history_path="data/history_v3.csv",universe_path="data/universe_history.csv"):
    wb=Workbook(); scored=[r for r in rows if r["opportunity_score"] is not None]
    ws=wb.active; ws.title="Executive Summary"
    ws["A1"]="EGX100 V3 Fundamental Research Report"; ws["A1"].font=Font(bold=True,size=18)
    ws["A2"]=f"Generated: {date.today():%d %B %Y}"
    ws["A3"]=f"Universe: {len(rows)} | Scored: {len(scored)} | Sector-specific valuation + forward validation"
    stats=[("Stocks scored",len(scored)),("High confidence",sum(r["confidence"]=="High" for r in scored)),("Review Required",sum(r["research_status"]=="Review Required" for r in scored)),("Median base upside",None)]
    ups=sorted((r["fair_value_base"]-r["price"])/r["price"] for r in scored if r["fair_value_base"] and r["price"])
    stats[-1]=(stats[-1][0],ups[len(ups)//2] if ups else None)
    for i,(k,v) in enumerate(stats,6): ws.cell(i,1,k); ws.cell(i,2,v)
    if stats[-1][1] is not None: ws["B9"].number_format="+0.0%"
    ws["A12"]="Top 15 V3 Research Opportunities"; ws["A12"].font=Font(bold=True,size=13)
    h=["Rank","Ticker","Sector","Price","Base FV","Base Upside","Bear FV","Bull FV","Methods","Dispersion","Valuation","Quality","Confidence","Confidence Score","Coverage","Opportunity","Status","Research Signal"]
    header(ws,13,h)
    for i,r in enumerate(scored[:15],14):
        row=[r["rank"],r["ticker"],r["sector"],r["price"],r["fair_value_base"],((r["fair_value_base"]-r["price"])/r["price"] if r["fair_value_base"] and r["price"] else None),r["fair_value_bear"],r["fair_value_bull"],", ".join(r["applicable_methods"]),r["dispersion"],r["valuation_score"],r["quality_score"],r["confidence"],r["confidence_score"],r["valuation_coverage"],r["opportunity_score"],r["research_status"],r.get("research_signal")]
        for j,v in enumerate(row,1): ws.cell(i,j,v).border=BORDER
        for j in (6,10,15): ws.cell(i,j).number_format="0.0%" if j!=15 else "0%"
        ws.cell(i,13).fill=PatternFill("solid",fgColor=GREEN if r["confidence"]=="High" else YELLOW if r["confidence"]=="Medium" else RED)
    ws.freeze_panes="A14"
    for j,w in enumerate([7,10,22,11,12,13,12,12,38,12,12,11,13,15,11,12,12,24],1): ws.column_dimensions[get_column_letter(j)].width=w

    rd=wb.create_sheet("V3 Ranking")
    h=["Rank","Ticker","Company","Sector","Sector Source","Sector Confidence","Data Source","Price","Bear FV","Base FV","Bull FV","Base Upside","InvestingPro FV","InvestingPro Upside","FV Gap vs V3","Dispersion","Valuation Score","Quality Score","Confidence","Confidence Score","Coverage","Opportunity Score","Research Signal","Red Flags"]
    header(rd,1,h)
    for i,r in enumerate(rows,2):
        vals=[r["rank"],r["ticker"],r.get("company_name") or "",r["sector"],r.get("sector_source"),r.get("sector_confidence"),r.get("data_source"),r["price"],r["fair_value_bear"],r["fair_value_base"],r["fair_value_bull"],((r["fair_value_base"]-r["price"])/r["price"] if r["fair_value_base"] and r["price"] else None),r.get("investingpro_fair_value"),r.get("investingpro_fair_value_upside"),((r.get("investingpro_fair_value")-r["fair_value_base"])/r["fair_value_base"] if r.get("investingpro_fair_value") and r.get("fair_value_base") else None),r["dispersion"],r["valuation_score"],r["quality_score"],r["confidence"],r["confidence_score"],r["valuation_coverage"],r["opportunity_score"],r.get("research_signal"),"; ".join(r["red_flags"])]
        for j,v in enumerate(vals,1): rd.cell(i,j,v).border=BORDER
        for j in (12,14,15,16,21): rd.cell(i,j).number_format="0.0%" if j!=21 else "0%"
    rd.auto_filter.ref=f"A1:U{len(rows)+1}"; rd.freeze_panes="H2"

    vd=wb.create_sheet("Valuation Detail")
    h=["Ticker","Sector","Price","DPS","Payout Ratio","P/E FV","P/B FV","Residual Income FV","DDM FV","DCF FV","EV/EBITDA FV","Book NAV Proxy","SOTP FV","V3 Bear FV","V3 Base FV","V3 Bull FV","InvestingPro FV","InvestingPro Upside","FV Gap vs V3","InvestingPro As Of","InvestingPro Status","Dispersion","Coverage","Notes"]
    header(vd,1,h)
    for i,r in enumerate(rows,2):
        v=r["valuations"]; notes="; ".join(r["red_flags"])
        vals=[r["ticker"],r["sector"],r["price"],r.get("dividend_per_share"),r.get("dividend_payout_ratio"),v.get("pe"),v.get("pb"),v.get("residual_income"),v.get("ddm"),v.get("dcf"),v.get("ev_ebitda"),v.get("book_nav_proxy"),v.get("sotp"),r["fair_value_bear"],r["fair_value_base"],r["fair_value_bull"],r.get("investingpro_fair_value"),r.get("investingpro_fair_value_upside"),((r.get("investingpro_fair_value")-r["fair_value_base"])/r["fair_value_base"] if r.get("investingpro_fair_value") and r.get("fair_value_base") else None),r.get("investingpro_as_of_date"),r.get("investingpro_status"),r["dispersion"],r["valuation_coverage"],notes]
        for j,x in enumerate(vals,1): vd.cell(i,j,x).border=BORDER
        for j in (18,19,22): vd.cell(i,j).number_format="0.0%" if j!=22 else "0%"

    sec=wb.create_sheet("Sector Dashboard")
    header(sec,1,["Sector","Stocks","Median Base Upside","Avg Opportunity","Avg Quality","Avg Confidence","Median Coverage","Review Required"])
    groups={}
    for r in scored: groups.setdefault(r["sector"],[]).append(r)
    for i,(s,a) in enumerate(sorted(groups.items()),2):
        ups=sorted((r["fair_value_base"]-r["price"])/r["price"] for r in a if r["fair_value_base"] and r["price"])
        med=ups[len(ups)//2] if ups else None
        row=[s,len(a),med,sum((r["opportunity_score"] or 0) for r in a)/len(a),sum((r["quality_score"] or 0) for r in a)/len(a),sum(r["confidence_score"] for r in a)/len(a),sum(r["valuation_coverage"] for r in a)/len(a),sum(r["research_status"]=="Review Required" for r in a)/len(a)]
        for j,x in enumerate(row,1): sec.cell(i,j,x).border=BORDER
        for j in (3,8): sec.cell(i,j).number_format="0.0%"
        sec.cell(i,7).number_format="0%"

    rf=wb.create_sheet("Red Flags")
    header(rf,1,["Rank","Ticker","Sector","Status","Confidence","Red Flags"])
    for i,r in enumerate([x for x in rows if x["red_flags"]],2):
        vals=[r["rank"],r["ticker"],r["sector"],r["research_status"],r["confidence"],"; ".join(r["red_flags"])]
        for j,x in enumerate(vals,1): rf.cell(i,j,x).border=BORDER
        rf.cell(i,6).alignment=Alignment(wrap_text=True)

    hist=wb.create_sheet("Historical Signals")
    hp=Path(history_path)
    if hp.exists():
        data=list(csv.reader(hp.open("r",encoding="utf-8")))
        for row in data: hist.append(row)
    else: hist.append(["No V3 history yet."])

    bt=wb.create_sheet("Forward Validation")
    summary,observations,buckets,conf_summary,signal_summary,sector_summary=evaluate(history_path)
    header(bt,1,["Horizon","Observations","Scored Observations","Average Return","Median Return","Positive Rate","Average Opportunity Score"])
    for i,s in enumerate(summary,2):
        bt.append([s["group"],s["observations"],s["scored_observations"],s["avg_return"],s["median_return"],s["positive_rate"],s["avg_score"]])
        for j in (4,5,6): bt.cell(i,j).number_format="0.0%"
    if not summary: bt.append(["Not enough future observations yet. V3 requires later weekly snapshots before a horizon can be evaluated."])
    bt["A8"]="Score-Bucket Backtest"; bt["A8"].font=Font(bold=True,size=13)
    header(bt,9,["Horizon","Score Bucket","Observations","Average Return","Median Return","Positive Rate"])
    row=10
    for s in buckets:
        bt.append([s["horizon"],s["group"],s["observations"],s["avg_return"],s["median_return"],s["positive_rate"]])
        for j in (4,5,6): bt.cell(row,j).number_format="0.0%"
        row+=1
    conf=wb.create_sheet("Backtest Diagnostics")
    header(conf,1,["Dimension","Horizon","Group","Observations","Average Return","Median Return","Positive Rate","Average Score"])
    row=2
    for title,data in [("Confidence",conf_summary),("Research Signal",signal_summary),("Sector",sector_summary)]:
        for s in data:
            conf.append([title,s["horizon"],s["group"],s["observations"],s["avg_return"],s["median_return"],s["positive_rate"],s["avg_score"]])
            for j in (5,6,7): conf.cell(row,j).number_format="0.0%"
            row+=1
    audit=wb.create_sheet("Research Audit")
    header(audit,1,["Audit Item","Current State","Interpretation"])
    audit_rows=[
      ("Universe size",len(rows),"Expected 100 active members; verify against the latest official EGX constituent extract."),
      ("Unique tickers",len({r["ticker"] for r in rows}),"Should equal universe size."),
      ("Sector registry coverage",sum(r.get("sector_source")=="Controlled sector registry" for r in rows),"Registry-based classifications are the most auditable current mapping."),
      ("Low sector confidence",sum(r.get("sector_confidence")=="Low" for r in rows),"Requires manual classification review."),
      ("Stock data source","StockAnalysis.com scrape","External scraped source; reconcile material fields to company/EGX disclosures before commercial use."),
      ("Universe source","V2.6 configured EGX30 + EGX70 fallback","Replace with official dated EGX constituent extract when available."),
      ("Backtest observations",len(observations),"Only completed future horizons are included; missing future prices are not fabricated."),
      ("InvestingPro Fair Value coverage",sum(r.get("investingpro_fair_value") is not None for r in rows),"Only verified InvestingPro values are counted; locked/unverified values remain blank."),
    ]
    for i,rowv in enumerate(audit_rows,2):
        for j,x in enumerate(rowv,1): audit.cell(i,j,x).border=BORDER


    uv=wb.create_sheet("Universe History")
    up=Path(universe_path)
    if up.exists():
        for row in csv.reader(up.open("r",encoding="utf-8")): uv.append(row)
    else: uv.append(["No universe history yet."])

    mt=wb.create_sheet("V3 Methodology")
    mt.column_dimensions["A"].width=120
    notes=[
      "V3 is a quantitative research/screening system, not investment advice.",
      "Universe is dated and stored internally to reduce survivorship bias. The current V3 run uses the configured EGX30 + EGX70 fallback and should be reconciled to the latest official EGX constituent extract before commercial use.",
      "Banks/financials: P/E, P/B, Residual Income and DDM are economically appropriate when inputs exist.",
      "Residual Income starts from current BVPS and discounts excess returns over cost of equity; forecast ROE fades toward cost of equity.",
      "Real Estate: P/E, P/B, DCF, EV/EBITDA and Book NAV Proxy. Book NAV Proxy is explicitly not property-level NAV/SOTP.",
      "Holding Companies: SOTP is supported through an explicit component registry. If component data is absent, SOTP is not fabricated.",
      "Other corporates: P/E, DCF and EV/EBITDA.",
      "Base FV is the median of valid applicable methods. Bear/Bull are uncertainty bands around Base driven by valuation dispersion.",
      "Opportunity Score retains the V2.6 weights until enough historical observations exist to test whether they add predictive value. Do not retune weights weekly.",
      "Forward Validation measures 1/3/6/12-month realized price returns using only future weekly snapshots; it never invents missing prices.",
      "Backtest results are descriptive out-of-sample validation, not a promise of future returns. No commercial performance claim should be made until sufficient observations, benchmark context, and data-provenance reconciliation are available.",
      "InvestingPro Fair Value is an external benchmark and is not used to calculate V3 Base FV, Opportunity Score, or ranking. Exact values must come from a verified InvestingPro source/export; public pages may lock the value."
    ]
    for i,n in enumerate(notes,2): mt.cell(i,1,n); mt.cell(i,1).alignment=Alignment(wrap_text=True,vertical="top"); mt.row_dimensions[i].height=32
    for sh in wb.worksheets: sh.sheet_view.showGridLines=False
    Path(output_path).parent.mkdir(parents=True,exist_ok=True); wb.save(output_path); return output_path
