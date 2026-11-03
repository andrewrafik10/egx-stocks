# EGX100 V3.1 Fundamental Research Bot

V3.1 keeps the V3 sector-aware valuation engine and forward-validation history,
but makes the weekly user-facing report shorter and more decision-focused.

## Architecture

**Dated EGX100 universe → data collection → validation → sector classification →
sector-specific valuation → quality / confidence scoring → six-sheet Excel report
→ concise Telegram shortlist → internal historical data**

## Six-sheet workbook

1. **Market Overview** — universe coverage, shortlist count and sector snapshot.
2. **Top Opportunities** — at most 20 candidates that pass explicit upside,
   data-quality and confidence filters. The report is allowed to show fewer
   than 20 or none.
3. **Stock Analysis** — all universe members with a compact set of core metrics.
4. **Valuation Comparison** — V3 Bear / Base / Bull beside verified InvestingPro
   Fair Value, where available.
5. **Risk & Quality** — data completeness, valuation coverage, confidence,
   sector provenance and red flags for all stocks.
6. **Methodology & Sources** — assumptions, source limitations and disclosures.

The workbook intentionally excludes raw historical snapshots, universe history,
and detailed backtest diagnostics. These remain internal model data in GitHub.

## Data Quality Score

The transparent Data Quality Score combines:
- 40% data completeness;
- 30% valuation-method coverage;
- 15% sector-provenance confidence;
- 15% source confidence;
- a capped penalty for material red flags.

The current scraped data source receives a conservative source-confidence
component. A high score does not replace source verification.

## Sector valuation frameworks

- **Financials / banks:** P/E, P/B, Residual Income and DDM when inputs exist.
- **Real Estate:** P/E, P/B, DCF, EV/EBITDA and Book NAV Proxy.
- **Holding Companies:** SOTP only when explicit component data exists.
- **Other corporates:** P/E, DCF and EV/EBITDA.

V3 Base Fair Value is the median of valid applicable methods. Bear/Bull are
uncertainty bands around Base based on method dispersion.

## InvestingPro benchmark

InvestingPro Fair Value is an external comparison only; it does not feed the
V3 valuation, opportunity score or ranking. Exact values must be verified from
an InvestingPro source/export. Analyst target prices are never substituted.
Blank values mean unavailable or unverified.

## Historical validation

Weekly signal snapshots remain in `data/history_v3.csv`; dated universe
membership remains in `data/universe_history.csv`. Forward validation evaluates
1, 3, 6 and 12-month realized returns only when later observations exist.
Missing future prices are never fabricated. The detailed diagnostics are retained
internally and are not placed in the compact workbook.

## Data limitations and commercial-use caution

The current universe is the configured EGX30 + EGX70 fallback and must be
reconciled to the latest official dated EGX constituent list. Stock fundamentals
are currently sourced by scrape and should be reconciled to company disclosures
and EGX filings before commercial distribution. Sector mapping, source freshness,
thin peer groups and model assumptions can materially affect results.

## Development

V3.1 is developed on `v3-development`. V2.6 remains frozen while V3.1 is
validated.
