"""
Weekly EGX fundamental scan — entry point.
Run manually: python main.py
Scheduled via .github/workflows/weekly-fundamental-report.yml
"""

import logging
import config
from scraper import fetch_universe
from ranking import rank_universe
from report import build_report
from telegram_sender import send_messages

log = logging.getLogger(__name__)


def main():
    logging.info(f"Fetching fundamentals for {len(config.ALL_TICKERS)} tickers...")
    all_cf = fetch_universe(config.ALL_TICKERS)

    logging.info("Ranking...")
    ranked = rank_universe(all_cf)

    logging.info("Building report...")
    messages = build_report(ranked, top_n=15)

    logging.info("Sending to Telegram...")
    send_messages(messages)
    logging.info("Done.")


if __name__ == "__main__":
    main()
