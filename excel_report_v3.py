"""V3.1 concise, decision-focused Excel report.

The user-facing workbook is deliberately limited to six sheets. Full weekly
snapshots, universe history and forward-validation inputs remain internal.
"""
from pathlib import Path
from datetime import date
import csv
from statistics import median
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.formatting.rule import ColorScaleRule

NAVY="1F4E78"; WHITE="FFFFFF"; GREEN="C6EFCE"; YELLOW="FFEB9C"; RED="FFC7CE"
BORDER=Border(*(Side(style="thin",color="D9D9D9"),)*4)

def _header(ws, headers):
    for i,h in enumerate(headers,1):
        c=ws.cell(1,i,h); c.fill=PatternFill("solid",fgColor=NAVY)
        c.font=Font(color=WHITE,bold=True); c.alignment=Alignment(horizontal="center",vertical="center",wrap_text=True)
        c.border=BORDER
    ws.row_dimensions[1].height=32

def _write_rows(ws, rows):
    for row in rows:
        ws.append(row)
        for cell in ws[ws.max_row]:
            cell.border=BORDER
            cell.alignment=Alignment(vertical="top",wrap_text=(cell.column in (3,4,5,6,17,18)))
    ws.freeze_panes="A2"; ws.auto_filter.ref=ws.dimensions
    ws.sheet_view.showGridLines=False

def _format(ws, percent_cols=(), decimal_cols=(), score_cols=()):
    for col in percent_cols:
        for cells in ws.iter_cols(min_col=col,max_col=col,min_row=2):
            for cell in cells: cell.number_format="0.0%;[Red]-0.0%;-"
    for col in decimal_cols:
        for cells in ws.iter_cols(min_col=col,max_col=col,min_row=2):
            for cell in cells: cell.number_format="#,##0.00;[Red]-#,##0.00;-"
    for col in score_cols:
        for cells in ws.iter_cols(min_col=col,max_col=col,min_row=2):
            for cell in cells: cell.number_format="0.0"

def _upside(r):
    p=r.get("price"); fv=r.get("fair_value_base")
    return (fv-p)/p if fv is not None and p not in (None,0) else None

def _quality(r):
    if r.get("data_quality_score") is not None: return r["data_quality_score"]
    completeness=r.get("data_completeness") or 0
    coverage=(r.get("valuation_coverage") or 0)*100
    sector={"High":100,"Medium":70,"Low":30}.get(r.get("sector_confidence"),30)
    source=60 if r.get("data_source") else 30
    penalty=min(20,len(r.get("red_flags") or [])*3)
    return round(max(0,min(100,completeness*.4+coverage*.3+sector*.15+source*.15-penalty)),1)

def _candidate(r):
    up=_upside(r)
    return (r.get("opportunity_score") is not None and up is not None and up>0
            and _quality(r)>=65 and r.get("confidence") in ("High","Medium")
            and r.get("research_signal") not in ("Data Limited","Deep Research Required"))

def build_excel_v3(rows, output_path, history_path="data/history_v3.csv", universe_path="data/universe_history.csv"):
    wb=Workbook()
    scored=[r for r in rows if r.get("opportunity_score") is not None]
    candidates=sorted((r for r in rows if _candidate(r)),
                      key=lambda r:(r.get("opportunity_score") or 0,_quality(r)),reverse=True)[:20]

    # 1. Market Overview — only the metrics needed to orient the reader.
    ws=wb.active; ws.title="Market Overview"
    ws["A1"]="EGX100 | Weekly Fundamental Research"; ws["A1"].font=Font(bold=True,size=18,color=NAVY)
    ws["A2"]=f"Generated: {date.today():%d %B %Y}"
    ws["A3"]="Decision-focused V3.1 summary. Detailed model history and diagnostics remain internal."
    overview=[
        ("Universe",len(rows)),("Stocks with a usable opportunity score",len(scored)),
        ("Shortlisted opportunities",len(candidates)),
        ("High-confidence stocks",sum(r.get("confidence")=="High" for r in scored)),
        ("Acceptable / strong data quality",sum(_quality(r)>=65 for r in rows)),
        ("Stocks requiring review",sum(r.get("research_status")=="Review Required" for r in rows)),
        ("Median V3 base upside",median([_upside(r) for r in scored if _upside(r) is not None]) if any(_upside(r) is not None for r in scored) else None),
        ("InvestingPro FV verified",sum(r.get("investingpro_fair_value") is not None for r in rows)),
    ]
    for i,(k,v) in enumerate(overview,5):
        ws.cell(i,1,k).font=Font(bold=True); ws.cell(i,2,v).border=BORDER
    ws["B11"].number_format="0.0%;[Red]-0.0%;-"
    ws["A15"]="Sector Snapshot"; ws["A15"].font=Font(bold=True,size=13,color=NAVY)
    sector_headers=["Sector","Stocks","Median Base Upside","Avg Data Quality","High Confidence"]
    for j,h in enumerate(sector_headers,1): ws.cell(16,j,h)
    for cell in ws[16]:
        cell.fill=PatternFill("solid",fgColor=NAVY); cell.font=Font(color=WHITE,bold=True); cell.alignment=Alignment(wrap_text=True)
    groups={}
    for r in rows: groups.setdefault(r.get("sector") or "Unclassified",[]).append(r)
    for i,(sector,items) in enumerate(sorted(groups.items()),17):
        ups=[_upside(x) for x in items if _upside(x) is not None]
        vals=[sector,len(items),median(ups) if ups else None,round(sum(_quality(x) for x in items)/len(items),1),sum(x.get("confidence")=="High" for x in items)]
        for j,v in enumerate(vals,1): ws.cell(i,j,v).border=BORDER
        ws.cell(i,3).number_format="0.0%"
    ws.column_dimensions["A"].width=38
    for col in "BCDE": ws.column_dimensions[col].width=22
    ws.sheet_view.showGridLines=False

    # 2. Top Opportunities — a shortlist, never a forced top-20 list.
    top=wb.create_sheet("Top Opportunities")
    h=["Rank","Ticker","Company","Sector","Price","V3 Base FV","Base Upside","Data Quality","Quality Score","Confidence","Valuation Coverage","Research Signal","Key Risk"]
    _header(top,h)
    data=[]
    for r in candidates:
        flags=r.get("red_flags") or []
        data.append([r.get("rank"),r["ticker"],r.get("company_name") or "",r.get("sector"),r.get("price"),r.get("fair_value_base"),_upside(r),_quality(r),r.get("quality_score"),r.get("confidence"),r.get("valuation_coverage"),r.get("research_signal"),flags[0] if flags else "No flagged issue"])
    _write_rows(top,data); _format(top,percent_cols=(7,11),decimal_cols=(5,6),score_cols=(8,9))
    for col,w in enumerate([8,11,27,22,13,14,14,13,13,13,16,27,34],1): top.column_dimensions[get_column_letter(col)].width=w
    if not candidates: top.append(["No stocks currently pass the shortlist quality and confidence filters."])

    # 3. Stock Analysis — all 100 stocks, compact core metrics only.
    sa=wb.create_sheet("Stock Analysis")
    h=["Rank","Ticker","Company","Sector","Price","V3 Base FV","Base Upside","P/E","P/B","ROE","EPS Growth","Revenue Growth","Debt / Equity","FCF Margin","Quality Score","Data Quality","Confidence","Research Signal"]
    _header(sa,h); data=[]
    for r in rows:
        m=r.get("metrics") or {}
        data.append([r.get("rank"),r["ticker"],r.get("company_name") or "",r.get("sector"),r.get("price"),r.get("fair_value_base"),_upside(r),m.get("pe"),m.get("pb"),m.get("roe"),m.get("eps_growth"),m.get("revenue_growth"),m.get("debt_equity"),m.get("fcf_margin"),r.get("quality_score"),_quality(r),r.get("confidence"),r.get("research_signal")])
    _write_rows(sa,data); _format(sa,percent_cols=(7,10,11,12,13,14),decimal_cols=(5,6,8,9),score_cols=(15,16))
    for col,w in enumerate([8,11,27,22,13,14,14,10,10,11,13,15,14,13,13,13,13,27],1): sa.column_dimensions[get_column_letter(col)].width=w

    # 4. Valuation Comparison — V3 vs InvestingPro, without confusing target prices with FV.
    vc=wb.create_sheet("Valuation Comparison")
    h=["Ticker","Sector","Price","V3 Bear FV","V3 Base FV","V3 Bull FV","V3 Base Upside","InvestingPro FV","InvestingPro Upside","FV Gap vs V3","IP As Of","IP Verification Status","Methods Used","Dispersion"]
    _header(vc,h); data=[]
    for r in rows:
        ipfv=r.get("investingpro_fair_value"); base=r.get("fair_value_base")
        gap=(ipfv-base)/base if ipfv is not None and base not in (None,0) else None
        data.append([r["ticker"],r.get("sector"),r.get("price"),r.get("fair_value_bear"),base,r.get("fair_value_bull"),_upside(r),ipfv,r.get("investingpro_fair_value_upside"),gap,r.get("investingpro_as_of_date"),r.get("investingpro_status") or "Not supplied",r.get("methods_used"),r.get("dispersion")])
    _write_rows(vc,data); _format(vc,percent_cols=(7,9,10,14),decimal_cols=(3,4,5,6,8))
    for col,w in enumerate([11,22,13,14,14,14,14,16,16,14,14,25,13,13],1): vc.column_dimensions[get_column_letter(col)].width=w

    # 5. Risk & Quality — one compact exception list for all stocks.
    rq=wb.create_sheet("Risk & Quality")
    h=["Ticker","Sector","Data Quality","DQ Label","Data Completeness","Valuation Coverage","Confidence","Sector Confidence","Research Status","Research Signal","Red Flags"]
    _header(rq,h); data=[]
    for r in sorted(rows,key=lambda x:_quality(x)):
        data.append([r["ticker"],r.get("sector"),_quality(r),r.get("data_quality_label") or ("Acceptable" if _quality(r)>=65 else "Limited"),r.get("data_completeness"),r.get("valuation_coverage"),r.get("confidence_score"),r.get("sector_confidence"),r.get("research_status"),r.get("research_signal"),"; ".join(r.get("red_flags") or []) or "None"])
    _write_rows(rq,data); _format(rq,percent_cols=(6,),score_cols=(3,5,7))
    for col,w in enumerate([11,22,13,14,17,17,14,17,20,27,60],1): rq.column_dimensions[get_column_letter(col)].width=w

    # 6. Methodology & Sources — short, readable disclosure.
    mt=wb.create_sheet("Methodology & Sources")
    mt.column_dimensions["A"].width=34; mt.column_dimensions["B"].width=115
    notes=[
      ("Purpose","Weekly EGX100 fundamental research screen. This is research support, not investment advice."),
      ("Shortlist rule","Top Opportunities includes at most 20 stocks with positive V3 upside, Data Quality Score >=65, High/Medium confidence, and no Data Limited / Deep Research Required signal. Passing no stocks is a valid result."),
      ("Core metrics","Price, sector, V3 fair value and upside, P/E, P/B, ROE, EPS growth, revenue growth, debt/equity, FCF margin, quality, data quality, confidence and valuation coverage."),
      ("Data Quality Score","40% data completeness + 30% valuation-method coverage + 15% sector-provenance confidence + 15% source confidence, less a capped red-flag penalty. Current scraped source receives a conservative 60/100 source component."),
      ("Sector frameworks","Banks/financials: P/E, P/B, Residual Income and DDM where inputs exist. Real estate: P/E, P/B, DCF, EV/EBITDA and book NAV proxy. Holding companies: SOTP only with explicit component data. Other corporates: P/E, DCF and EV/EBITDA."),
      ("V3 Base FV","Median of valid applicable valuation methods. Bear/Bull are uncertainty bands based on method dispersion."),
      ("InvestingPro","Shown only when an exact InvestingPro Fair Value has been verified. Analyst target prices are not substituted. Blank values mean unavailable/unverified."),
      ("Primary data source","StockAnalysis.com scrape. Material financial figures must be reconciled against company disclosures and EGX filings before commercial distribution."),
      ("Universe","Configured EGX30 + EGX70 fallback. Reconcile to the latest official dated EGX constituent list before commercial use."),
      ("Historical data","Full weekly signal snapshots, universe membership and forward-validation inputs remain in internal GitHub data files; they are intentionally excluded from this concise workbook."),
      ("Model limitations","Sector mapping, scraped source freshness, thin peer groups, model assumptions and missing inputs can materially affect outputs. Review Risk & Quality before interpreting a valuation."),
    ]
    for i,(k,v) in enumerate(notes,1):
        mt.cell(i,1,k).font=Font(bold=True,color=NAVY); mt.cell(i,2,v).alignment=Alignment(wrap_text=True,vertical="top")
        mt.cell(i,1).border=BORDER; mt.cell(i,2).border=BORDER; mt.row_dimensions[i].height=42
    mt.sheet_view.showGridLines=False

    # Consistent workbook presentation.
    for sh in wb.worksheets:
        sh.sheet_view.showGridLines=False
        sh.sheet_properties.pageSetUpPr.fitToPage=True
        sh.page_setup.fitToWidth=1; sh.page_setup.fitToHeight=0
        sh.sheet_properties.outlinePr.summaryBelow=True
    Path(output_path).parent.mkdir(parents=True,exist_ok=True)
    wb.save(output_path)
    return output_path
