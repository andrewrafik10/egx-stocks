"""
Weekly EGX fundamental scan — entry point.
Run manually: python main.py
Scheduled via .github/workflows/weekly-fundamental-report.yml
"""

import logging
from datetime import date

import config
from scraper import fetch_universe
from ranking import rank_universe
from report import build_report
from excel_report import build_excel
from telegram_sender import send_messages, send_document

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def main():
    log.info(f"Fetching fundamentals for {len(config.ALL_TICKERS)} tickers...")
    all_cf = fetch_universe(config.ALL_TICKERS)

    log.info("Ranking...")
    ranked = rank_universe(all_cf)

    log.info("Building Excel workbook...")
    excel_path = f"/tmp/egx_weekly_report_{date.today().isoformat()}.xlsx"
    build_excel(ranked, all_cf, excel_path)

    log.info("Sending Excel workbook to Telegram...")
    usable = sum(1 for r in ranked if r["composite_upside"] is not None)
    caption = f"EGX Weekly Fundamental Scan — {date.today().strftime('%d %b %Y')} ({usable}/{len(ranked)} scored)"
    send_document(excel_path, caption=caption)

    log.info("Sending short text summary too...")
    messages = build_report(ranked, top_n=10)
    send_messages(messages)

    log.info("Done.")


if __name__ == "__main__":
    main()
