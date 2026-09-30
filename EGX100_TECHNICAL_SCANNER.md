# EGX100 Technical Scanner

## Scope
Daily technical scan for the EGX100 working universe.

### Fields
- Latest completed close
- RSI(14)
- CCI(14)
- EMA(50)
- EMA(200)
- EMA50 vs EMA200
- Price vs EMA50 / EMA200
- Trend structure
- Rule-based chart pattern
- Bullish/bearish order-block zone and price relationship

## Pattern engine
The scanner only reports a named pattern when objective geometry passes the configured tolerance rules. Supported patterns currently include:
- Rising wedge
- Falling wedge
- Ascending channel
- Descending channel
- Double bottom / top
- Triple bottom / top
- No reliable pattern

This is a screening engine, not a discretionary chart annotation system.

## Order blocks
A bullish order block is defined as the last bearish candle before a strong bullish displacement that breaks a recent swing high. The bearish definition is the mirror image. The report gives the zone boundaries and whether the latest close is inside, above, or below the zone.

## Data
Historical OHLCV is pulled from Yahoo Finance's chart endpoint using the EGX Reuters-style .CA symbol convention. The scan requires at least 210 daily observations so EMA200 is based on sufficient history.

## Automation
The GitHub Actions workflow runs manually or after the Egyptian trading session on Sunday-Thursday and stores CSV/XLSX artifacts in output/.

## Next upgrades
1. Validate the 100-ticker manifest against the official EGX100 review file.
2. Add company names and sectors to the technical output.
3. Add support/resistance and breakout distance.
4. Add volume confirmation and relative-volume signals.
5. Join technical output to the existing fundamental/fair-value ranking.
6. Backtest pattern + momentum combinations before using them as a signal.