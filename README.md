# EGX Weekly Fundamental Bot

Scrapes fundamentals for EGX30 + EGX70 from stockanalysis.com, values each
stock four ways (P/E vs sector, Graham Number, simplified DCF, EV/EBITDA
comps), blends them into a ranked opportunity list, and sends it to Telegram
every Friday via GitHub Actions.

## Setup

1. `pip install -r requirements.txt`
2. Create a Telegram bot via @BotFather, get the token, and get your chat ID
   (message the bot once, then hit `https://api.telegram.org/bot<TOKEN>/getUpdates`)
3. Set env vars locally to test:
   ```
   export TELEGRAM_BOT_TOKEN=...
   export TELEGRAM_CHAT_ID=...
   python main.py
   ```
4. For GitHub Actions: add `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` as
   repo secrets (Settings → Secrets and variables → Actions). The workflow
   in `.github/workflows/weekly-fundamental-report.yml` runs every Friday
   16:00 UTC and can also be triggered manually from the Actions tab.

## What's genuinely solid here vs. what needs your judgment

**Solid:**
- Data source coverage (stockanalysis.com does cover all ~229 EGX tickers
  with multi-year financials, confirmed by inspection)
- The four valuation mechanics themselves (formulas are standard)
- Ranking logic re-normalizes weights when a method doesn't apply to a
  given stock, rather than silently zeroing it out

**Needs your judgment / tuning before you trust the output:**
1. **EGX30/EGX70 constituent lists in `config.py` are a market-cap-ranked
   starting point, not the official index membership** — EGX reviews and
   changes constituents twice a year. Verify against egx.com.eg before
   relying on this.
2. **Cost of equity / WACC is one flat 25% assumption for the whole market**
   (`config.py`). Your own modeling portfolio uses CAPM-derived rates that
   differ meaningfully by company (~23-24% for ETEL, ~27-28% for COMI) —
   the bot would benefit a lot from a per-sector or per-stock rate rather
   than one number for everyone. Straightforward to extend: add a
   `sector_cost_of_equity` dict and look it up in `dcf_valuation()`.
3. **Sector buckets are currently just "financials vs. everyone else"**
   (`ranking.py: sector_benchmarks()`) for computing peer P/E and EV/EBITDA
   medians. Real comps work wants tighter peer groups (banks vs. real
   estate vs. consumer, etc.) — worth mapping each ticker to a proper
   sector tag.
4. **Graham Number is structurally weak for banks** (book value doesn't
   mean the same thing for a leveraged balance sheet) — it's down-weighted
   for tickers in `FINANCIAL_SECTOR_TICKERS`, not excluded. You may prefer
   to exclude it outright for financials.
5. **HTML table matching in `scraper.py` uses text-label matching**
   (`"Net Income$"`, `"Book Value Per Share"`, etc.) against stockanalysis.com's
   current row labels. If they change their page layout, these will silently
   return `None` rather than error loudly — worth a periodic spot-check,
   and each `CompanyFundamentals.errors` list flags what's missing per ticker
   so you can see coverage gaps in the logs.
6. **Not tested end-to-end** — I don't have network access to
   stockanalysis.com from this sandbox to run it live, so treat the first
   run as a debugging pass. Start with `workflow_dispatch` (manual trigger)
   before trusting the Friday schedule.

## Extending

- Swap the flat sector bucket for real GICS-style sectors
- Add a second Telegram message with the full-universe CSV attached
  (Telegram supports document uploads via `sendDocument`)
- Track week-over-week rank changes (store last week's ranking in a JSON
  file committed back to the repo, or in a small SQLite DB)
- Feed the same fundamentals into your Excel-based sensitivity tables
  for names that make the top 15
