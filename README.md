# EGX100 V3 Fundamental Research Bot

V3 is the next research layer after the frozen V2.6 engine. It keeps the V2.6
history intact while adding sector-specific valuation and forward validation.

## V3 architecture

**Dated EGX100 universe → data collection → validation → sector classification →
sector-specific valuation → quality/valuation/confidence → research signals →
one Excel workbook → Telegram → internal historical CSV**

### Sector valuation frameworks

- **Financials / banks:** P/E, P/B, Residual Income and DDM when inputs exist.
- **Real Estate:** P/E, P/B, DCF, EV/EBITDA and Book NAV Proxy.
- **Holding Companies:** SOTP is supported through an explicit component registry;
  V3 never fabricates subsidiary values.
- **Other corporates:** P/E, DCF and EV/EBITDA.

The base fair value is the median of valid applicable methods. Bear/Bull are
uncertainty bands around Base based on method dispersion, not separate forecasts.

## Validation

V3 stores weekly signal snapshots in `data/history_v3.csv` and measures
realized returns at **1, 3, 6 and 12 months** once future observations exist.

V3 does not claim predictive performance until enough out-of-sample observations
have accumulated.

## Universe integrity

V3 stores dated membership snapshots in `data/universe_history.csv` to reduce
survivorship bias. The current branch preserves the verified V2.6 configured
EGX30 + EGX70 universe as a fallback; official EGX constituent extracts should
supersede that fallback when available.

The EGX publishes index constituent and methodology information through its
index pages and periodic reviews.

## Output policy

The weekly user-facing deliverable remains **one Excel workbook**. Historical
CSV files are internal model state committed to GitHub.

## Development

V3 is being developed on `v3-development`. V2.6 remains frozen and is not
rewritten while V3 is validated.


## V3 validation discipline

V3 now stores auditable sector provenance, data-source labels, and a research-signal classification. The weekly workbook includes Research Audit, Forward Validation, and Backtest Diagnostics.

Backtesting is strictly out-of-sample: a signal dated T is evaluated only against a later stored price at or beyond 1/3/6/12 months. The engine also reports performance by Opportunity Score bucket, confidence, research signal, and sector. Missing future observations are skipped rather than fabricated.

The Opportunity Score weights are intentionally frozen while observations accumulate. They should only be reconsidered after a meaningful out-of-sample sample exists.

The current universe remains the configured EGX30 + EGX70 fallback and must be reconciled against the latest official EGX constituent extract before commercial use. Stock fundamentals are currently sourced by scrape and should be reconciled to company/EGX disclosures for material fields.
