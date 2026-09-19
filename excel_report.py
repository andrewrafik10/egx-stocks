"""
Builds the weekly Excel deliverable: every EGX30/EGX70 ticker, every valuation
method's fair value and implied upside, blended composite score, and rank.

Formatting conventions (matching the style used across the rest of the
modeling portfolio): bold header row, frozen panes, percentage formatting,
color-scale conditional formatting on the upside columns (red = downside,
green = upside), light shading to flag banks/financials where Graham is
structurally weaker.
"""

from datetime import date

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.utils import get_column_letter

HEADER_FILL = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
HEADER_FONT = Font(color="FFFFFF", bold=True)
FINANCIAL_FILL = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid")
THIN_BORDER = Border(*(Side(style="thin", color="D9D9D9"),) * 4)

COLUMNS = [
    ("Rank", 6),
    ("Ticker", 10),
    ("Type", 10),
    ("Price", 10),
    ("EPS", 10),
    ("BVPS", 10),
    ("Revenue", 14),
    ("Net Income", 14),
    ("EBITDA", 14),
    ("P/E Fair Value", 14),
    ("P/E Upside", 12),
    ("Graham Fair Value", 16),
    ("Graham Upside", 14),
    ("DCF Fair Value", 14),
    ("DCF Upside", 12),
    ("Comps Fair Value", 14),
    ("Comps Upside", 12),
    ("Composite Upside", 16),
    ("Methods Used", 12),
    ("Notes", 40),
]

PERCENT_COLS = {"P/E Upside", "Graham Upside", "DCF Upside", "Comps Upside", "Composite Upside"}
NUMBER_COLS = {"Price", "EPS", "BVPS", "P/E Fair Value", "Graham Fair Value", "DCF Fair Value", "Comps Fair Value"}
BIG_NUMBER_COLS = {"Revenue", "Net Income", "EBITDA"}


def build_excel(ranked: list, all_cf: dict, output_path: str) -> str:
    wb = Workbook()
    ws = wb.active
    ws.title = "EGX Weekly Ranking"

    for col_idx, (name, width) in enumerate(COLUMNS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=name)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center")
        ws.column_dimensions[get_column_letter(col_idx)].width = width
    ws.freeze_panes = "C2"

    col_index = {name: i + 1 for i, (name, _) in enumerate(COLUMNS)}

    for rank, r in enumerate(ranked, start=1):
        row = rank + 1
        cf = all_cf.get(r["ticker"])
        mr = r["method_results"]

        def fv(method):
            return mr.get(method, {}).get("fair_value")

        def up(method):
            return r["upsides"].get(method)

        values = {
            "Rank": rank,
            "Ticker": r["ticker"],
            "Type": "Financial" if r["is_financial"] else "Other",
            "Price": r["price"],
            "EPS": cf.eps if cf else None,
            "BVPS": cf.book_value_per_share if cf else None,
            "Revenue": cf.revenue if cf else None,
            "Net Income": cf.net_income if cf else None,
            "EBITDA": cf.ebitda if cf else None,
            "P/E Fair Value": fv("pe"),
            "P/E Upside": up("pe"),
            "Graham Fair Value": fv("graham"),
            "Graham Upside": up("graham"),
            "DCF Fair Value": fv("dcf"),
            "DCF Upside": up("dcf"),
            "Comps Fair Value": fv("comps"),
            "Comps Upside": up("comps"),
            "Composite Upside": r["composite_upside"],
            "Methods Used": r["methods_used"],
            "Notes": "; ".join(r["errors"]) if r["errors"] else "",
        }

        for name, value in values.items():
            c = ws.cell(row=row, column=col_index[name], value=value)
            c.border = THIN_BORDER
            if name in PERCENT_COLS and value is not None:
                c.number_format = "+0.0%;-0.0%"
            elif name in NUMBER_COLS and value is not None:
                c.number_format = "#,##0.00"
            elif name in BIG_NUMBER_COLS and value is not None:
                c.number_format = "#,##0,,\"M\""  # display in millions
            if r["is_financial"]:
                c.fill = FINANCIAL_FILL

    last_row = len(ranked) + 1
    if last_row > 1:
        for name in PERCENT_COLS:
            col_letter = get_column_letter(col_index[name])
            rng = f"{col_letter}2:{col_letter}{last_row}"
            ws.conditional_formatting.add(
                rng,
                ColorScaleRule(
                    start_type="min", start_color="F8696B",
                    mid_type="percentile", mid_value=50, mid_color="FFEB84",
                    end_type="max", end_color="63BE7B",
                ),
            )

    # Legend / notes sheet
    notes = wb.create_sheet("Notes")
    notes["A1"] = "EGX Weekly Fundamental Scan"
    notes["A1"].font = Font(bold=True, size=14)
    notes["A2"] = f"Generated {date.today().isoformat()}"
    lines = [
        "",
        "Composite Upside blends P/E, Graham Number, DCF, and Comparable (EV/EBITDA) valuation,",
        "re-weighting across whichever methods produced a usable fair value for that stock.",
        "",
        "Financial-sector rows (shaded) have Graham Number down-weighted, since book value",
        "is distorted by leverage for banks - treat that column with extra caution for those names.",
        "",
        "Methods Used = how many of the 4 methods contributed a fair value. Low coverage",
        "(1 or fewer) means the composite score is resting on a single, less reliable method.",
        "",
        "This is a screening signal built from a simplified, single-assumption model",
        "(one flat cost of equity, coarse sector benchmarks) - not a substitute for the",
        "line-by-line models in the IB portfolio work. Treat it as a starting shortlist,",
        "not a price target.",
    ]
    for i, line in enumerate(lines, start=3):
        notes[f"A{i}"] = line
    notes.column_dimensions["A"].width = 100

    wb.save(output_path)
    return output_path
