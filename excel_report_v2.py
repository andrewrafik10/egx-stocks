"""Commercial V2.6 Excel output."""
from datetime import date
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.chart import BarChart, Reference
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.utils import get_column_letter

NAVY="1F4E78"; WHITE="FFFFFF"; GREEN="C6EFCE"; YELLOW="FFEB9C"; RED="FFC7CE"
HEADER=PatternFill("solid",fgColor=NAVY); HF=Font(color=WHITE,bold=True)
BORDER=Border(*(Side(style="thin",color="D9D9D9"),)*4)

def _header(ws,row,headers):
    for i,h in enumerate(headers,1):
        c=ws.cell(row,i,h); c.fill=HEADER; c.font=HF; c.alignment=Alignment(horizontal="center",wrap_text=True); c.border=BORDER

def _pct(v): return v

def build_excel_v2(rows,all_cf,output_path):
    wb=Workbook()
    scored=[r for r in rows if r["opportunity_score"] is not None]
    ws=wb.active; ws.title="Executive Summary"
    ws["A1"]="EGX100 V2.6 Fundamental Research Report"; ws["A1"].font=Font(bold=True,size=18)
    ws["A2"]=f"Generated: {date.today():%d %B %Y}"
    ws["A3"]=f"Universe: {len(rows)} | Scored: {len(scored)} | V2.6 applicability + valuation + quality + confidence diagnostics"
    ws["A5"]="Research Snapshot"; ws["A5"].font=Font(bold=True,size=13)
    vals=[r for r in scored if r["fair_value_base"] and r["price"]]
    median_up=sorted((r["fair_value_base"]-r["price"])/r["price"] for r in vals)[len(vals)//2] if vals else None
    stats=[
        ("Stocks scored",len(scored)),("High confidence",sum(r["confidence"]=="High" for r in scored)),
        ("Medium confidence",sum(r["confidence"]=="Medium" for r in scored)),
        ("Low confidence",sum(r["confidence"]=="Low" for r in scored)),
        ("Review Required",sum(r["research_status"]=="Review Required" for r in scored)),
        ("Median base upside",median_up),
        ("Median valuation coverage",sorted(r["valuation_coverage"] for r in scored)[len(scored)//2] if scored else None)
    ]
    for i,(k,v) in enumerate(stats,7):
        ws.cell(i,1,k); ws.cell(i,2,v)
        if "upside" in k.lower() and v is not None: ws.cell(i,2).number_format="+0.0%"
        if "coverage" in k.lower() and v is not None: ws.cell(i,2).number_format="0%"
    ws["A16"]="Top 10 V2.6 Opportunities"; ws["A16"].font=Font(bold=True,size=13)
    headers=["Rank","Ticker","Sector","Price","Base FV","Base Upside","Bear FV","Bull FV","Dispersion","Valuation Score","Quality Score","Confidence","Confidence Score","Coverage","Data Completeness","Opportunity","Status"]
    _header(ws,17,headers)
    for i,r in enumerate(scored[:10],18):
        vals=[r["rank"],r["ticker"],r["sector"],r["price"],r["fair_value_base"],
              (r["fair_value_base"]-r["price"])/r["price"] if r["fair_value_base"] and r["price"] else None,
              r["fair_value_bear"],r["fair_value_bull"],r["dispersion"],r["valuation_score"],r["quality_score"],
              r["confidence"],r["confidence_score"],r["valuation_coverage"],r["data_completeness"]/100,r["opportunity_score"],r["research_status"]]
        for j,v in enumerate(vals,1): ws.cell(i,j,v).border=BORDER
        for j in (6,9): ws.cell(i,j).number_format="0.0%"
        for j in (14,15): ws.cell(i,j).number_format="0%"
        ws.cell(i,12).fill=PatternFill("solid",fgColor=GREEN if r["confidence"]=="High" else YELLOW if r["confidence"]=="Medium" else RED)
        ws.cell(i,17).fill=PatternFill("solid",fgColor=YELLOW if r["research_status"]=="Review Required" else GREEN)
    for j,w in enumerate([7,10,22,11,12,13,12,12,12,14,12,13,15,11,16,12,18],1):
        ws.column_dimensions[get_column_letter(j)].width=w
    ws.freeze_panes="A18"

    sec=wb.create_sheet("Sector Dashboard"); sec["A1"]="Sector Dashboard"; sec["A1"].font=Font(bold=True,size=16)
    groups={}
    for r in scored: groups.setdefault(r["sector"],[]).append(r)
    sh=["Sector","Stocks","Median Base Upside","Avg Opportunity","Avg Quality","Avg Confidence","Median Coverage","% Review Required","Median P/E","Median P/B","Median ROE","Median EPS CAGR","Median Revenue CAGR"]
    _header(sec,3,sh)
    for i,(s,items) in enumerate(sorted(groups.items()),4):
        def med(key):
            a=sorted(x for x in key if x is not None); return a[len(a)//2] if a else None
        ups=med([(r["fair_value_base"]-r["price"])/r["price"] for r in items if r["fair_value_base"] and r["price"]])
        ms=[r["metrics"]["pe"] for r in items]; pb=[r["metrics"]["pb"] for r in items]
        roe=[r["metrics"]["roe"] for r in items]; eg=[r["metrics"]["eps_growth"] for r in items]; rg=[r["metrics"]["revenue_growth"] for r in items]
        row=[s,len(items),ups,sum(r["opportunity_score"] for r in items)/len(items),sum((r["quality_score"] or 0) for r in items)/len(items),sum(r["confidence_score"] for r in items)/len(items),sum(r["valuation_coverage"] for r in items)/len(items),sum(r["research_status"]=="Review Required" for r in items)/len(items),med(ms),med(pb),med(roe),med(eg),med(rg)]
        for j,v in enumerate(row,1): sec.cell(i,j,v).border=BORDER
        for j in (3,8,12,13): sec.cell(i,j).number_format="0.0%"
        sec.cell(i,7).number_format="0%"
        sec.cell(i,11).number_format="0.0%"
    chart=BarChart(); chart.title="Median Base Upside by Sector"; chart.y_axis.title="Upside"; chart.x_axis.title="Sector"
    chart.add_data(Reference(sec,min_col=3,min_row=3,max_row=3+len(groups)),titles_from_data=True)
    chart.set_categories(Reference(sec,min_col=1,min_row=4,max_row=3+len(groups))); sec.add_chart(chart,"O3")

    fr=wb.create_sheet("V2.6 Ranking")
    headers=["Rank","Ticker","Company","Sector","Price","Bear FV","Base FV","Bull FV","Base Upside","Dispersion","Valuation Score","Quality Score","Confidence","Confidence Score","Coverage","Data Completeness","Opportunity Score","Status","Applicable Methods","Methods Used","P/E","P/B","DCF","EV/EBITDA","ROE","Net Margin","EBITDA Margin","FCF Margin","Debt/Equity","EPS CAGR","Revenue CAGR","Beta","Cost of Equity","COE Source","Red Flags","Data Errors"]
    _header(fr,1,headers); fr.freeze_panes="E2"
    for i,r in enumerate(rows,2):
        m=r["metrics"]; v=r["valuations"]
        values=[r["rank"],r["ticker"],r.get("company_name") or "",r["sector"],r["price"],r["fair_value_bear"],r["fair_value_base"],r["fair_value_bull"],
        (r["fair_value_base"]-r["price"])/r["price"] if r["fair_value_base"] and r["price"] else None,r["dispersion"],r["valuation_score"],r["quality_score"],r["confidence"],r["confidence_score"],r["valuation_coverage"],r["data_completeness"]/100,r["opportunity_score"],r["research_status"],", ".join(r["applicable_methods"]),r["methods_used"],m["pe"],m["pb"],v.get("dcf"),v.get("comps"),m["roe"],m["net_margin"],m["ebitda_margin"],m["fcf_margin"],m["debt_equity"],m["eps_growth"],m["revenue_growth"],m["beta"],r["discount_rate"],r["discount_rate_source"],"; ".join(r["red_flags"]),"; ".join(r["errors"])]
        for j,x in enumerate(values,1): fr.cell(i,j,x).border=BORDER
        for j in (9,10,15,16,25,26,27,28,30,31): fr.cell(i,j).number_format="0.0%"
        for j in (15,16): fr.cell(i,j).number_format="0%"
        fr.cell(i,13).fill=PatternFill("solid",fgColor=GREEN if r["confidence"]=="High" else YELLOW if r["confidence"]=="Medium" else RED)
        fr.cell(i,18).fill=PatternFill("solid",fgColor=YELLOW if r["research_status"]=="Review Required" else GREEN)
    for j,w in enumerate([7,10,30,20,10,11,11,11,13,13,14,12,13,15,11,16,15,18,28,10,9,9,10,11,10,12,14,12,12,11,12,9,14,12,42,35],1): fr.column_dimensions[get_column_letter(j)].width=w
    fr.auto_filter.ref=f"A1:{get_column_letter(len(headers))}{len(rows)+1}"
    for col in (9,10,17,25,26,27,28,30,31):
        fr.conditional_formatting.add(f"{get_column_letter(col)}2:{get_column_letter(col)}{len(rows)+1}",ColorScaleRule(start_type="min",start_color="F8696B",mid_type="percentile",mid_value=50,mid_color="FFEB84",end_type="max",end_color="63BE7B"))

    vd=wb.create_sheet("Valuation Detail")
    _header(vd,1,["Ticker","Company","Sector","Price","P/E FV","P/B FV","DCF FV","EV/EBITDA FV","Bear FV","Base FV","Bull FV","Base Upside","Dispersion","Coverage","Applicable Methods","Methods Used","Valuation Score","Peer P/E","Peer P/B","Peer EV/EBITDA"])
    for i,r in enumerate(rows,2):
        v=r["valuations"]; p=r["peer"]
        vals=[r["ticker"],r.get("company_name") or "",r["sector"],r["price"],v.get("pe"),v.get("pb"),v.get("dcf"),v.get("comps"),r["fair_value_bear"],r["fair_value_base"],r["fair_value_bull"],(r["fair_value_base"]-r["price"])/r["price"] if r["fair_value_base"] and r["price"] else None,r["dispersion"],r["valuation_coverage"],", ".join(r["applicable_methods"]),r["methods_used"],r["valuation_score"],p.get("pe"),p.get("pb"),p.get("ev_ebitda")]
        for j,x in enumerate(vals,1): vd.cell(i,j,x).border=BORDER
        for j in (12,13,14): vd.cell(i,j).number_format="0.0%" if j!=14 else "0%"

    rf=wb.create_sheet("Red Flags")
    _header(rf,1,["Rank","Ticker","Company","Sector","Opportunity Score","Confidence","Status","Red Flags","Data Errors"])
    for i,r in enumerate([x for x in rows if x["red_flags"] or x["errors"]],2):
        vals=[r["rank"],r["ticker"],r.get("company_name") or "",r["sector"],r["opportunity_score"],r["confidence"],r["research_status"],"; ".join(r["red_flags"]),"; ".join(r["errors"])]
        for j,x in enumerate(vals,1): rf.cell(i,j,x).border=BORDER
        rf.cell(i,8).alignment=Alignment(wrap_text=True)
        rf.cell(i,9).alignment=Alignment(wrap_text=True)
    for j,w in enumerate([7,10,30,20,15,13,18,60,45],1): rf.column_dimensions[get_column_letter(j)].width=w

    mt=wb.create_sheet("Methodology"); mt.column_dimensions["A"].width=125
    mt["A1"]="V2.6 Methodology & Audit Notes"; mt["A1"].font=Font(bold=True,size=16)
    notes=[
        "V2.6 is an automated quantitative research/screening model, not investment advice.",
        "Sector classification: controlled EGX100 ticker taxonomy takes priority over scraped industry text. Unknown names remain Unclassified.",
        "Financials: P/E and peer P/B are the primary screening methods; generic corporate DCF/EV-EBITDA are excluded.",
        "Real Estate: P/E/PB, DCF and EV/EBITDA may be used when inputs are valid. A true property NAV/SOTP engine remains a future upgrade.",
        "Other corporates: P/E, DCF and EV/EBITDA are used only when the method is economically applicable and its core inputs exist.",
        "Valuation applicability is separated from data availability. Valuation Coverage = usable applicable methods / applicable methods.",
        "Base Fair Value = median of valid applicable valuation methods. Bear/Base/Bull are a research uncertainty range around Base, driven by method dispersion; they are not separate earnings forecasts.",
        "Valuation Dispersion = (max valid method FV - min valid method FV) / Base FV. High dispersion is explicitly treated as uncertainty.",
        "Quality Score evaluates available profitability, growth, FCF conversion and leverage signals. It is not a forecast.",
        "Valuation Score converts the base valuation gap into a bounded 0-100 research score.",
        "Confidence Score combines data completeness, valuation coverage, quality, method agreement and sector classification.",
        "Opportunity Score combines Valuation Score, Quality Score and Confidence Score using configured research weights. These weights are assumptions and must be validated by the historical backtest before commercial use.",
        "Red Flags identify missing core data, low method coverage, extreme valuation disagreement, negative FCF, leverage concerns, weak growth and unresolved classification.",
        "DCF discount rate uses stock-level CAPM when beta is available: risk-free rate + beta × Egypt ERP. If beta is unavailable, the configured fallback is explicitly recorded.",
        "Peer multiples use the controlled macro-sector peer group. Thin groups may use the configured sector P/E fallback; this is disclosed in the peer fields.",
        "Data source is the current automated financial scrape. Before client distribution, key financials and assumptions should be reconciled with official EGX/company disclosures and timestamped.",
        "Historical Signals and Backtest sheets are designed to accumulate weekly observations. No performance claim should be made until enough future observations exist."
    ]
    for i,n in enumerate(notes,3):
        mt.cell(i,1,n); mt.cell(i,1).alignment=Alignment(wrap_text=True,vertical="top"); mt.row_dimensions[i].height=32

    for ws in wb.worksheets:
        ws.sheet_view.showGridLines=False
    output=Path(output_path); output.parent.mkdir(parents=True,exist_ok=True)
    wb.save(output); return output
