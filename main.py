"""
Weekly EGX fundamental scan — entry point.
Run manually: python main.py
Scheduled via .github/workflows/weekly-fundamental-report.yml
"""

import logging
from datetime import date
from pathlib import Path

import config
from scraper import fetch_universe
from v2_engine import rank_v2
from report import build_report
from excel_report_v2 import build_excel_v2
from telegram_sender import send_messages, send_document

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def main():
    log.info(f"Fetching fundamentals for {len(config.ALL_TICKERS)} tickers...")
    all_cf = fetch_universe(config.ALL_TICKERS)

    log.info("Running V2 sector-aware research engine...")
    ranked = rank_v2(all_cf)

    log.info("Building Excel workbook...")
    # اكتب داخل workspace (أثبت على GitHub Actions من /tmp)
    out_dir = Path.cwd() / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    excel_path = out_dir / f"egx_weekly_v2_report_{date.today().isoformat()}.xlsx"

    build_excel_v2(ranked, all_cf, str(excel_path))

    if not excel_path.exists() or excel_path.stat().st_size == 0:
        raise FileNotFoundError(
            f"Excel was not created or is empty: {excel_path.resolve()}"
        )

    log.info("Excel saved: %s (%s bytes)", excel_path.resolve(), excel_path.stat().st_size)

    log.info("Sending Excel workbook to Telegram...")
    usable = sum(1 for r in ranked if r.get("opportunity_score") is not None)
    caption = (
        f"EGX Weekly Fundamental Scan — {date.today().strftime('%d %b %Y')} "
        f"({usable}/{len(ranked)} scored)"
    )
    send_document(str(excel_path), caption=caption)

    log.info("Sending short text summary too...")
    messages = build_report(ranked, top_n=10)
    send_messages(messages)

    log.info("Done.")


if __name__ == "__main__":
    main()
