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
index pages and periodic reviews. citeturn0search0turn0search9

## Output policy

The weekly user-facing deliverable remains **one Excel workbook**. Historical
CSV files are internal model state committed to GitHub.

## Development

V3 is being developed on `v3-development`. V2.6 remains frozen and is not
rewritten while V3 is validated.
