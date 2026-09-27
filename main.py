"""EGX100 V3 weekly research pipeline."""
import logging
from datetime import date
from pathlib import Path
from universe_v3 import get_universe
from scraper import fetch_universe
from v3_engine import rank_v3
from history_store_v3 import append_snapshot
from excel_report_v3 import build_excel_v3
from report_v3 import build_report
from telegram_sender import send_messages,send_document
logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s")
log=logging.getLogger(__name__)
def main():
    members=get_universe()
    tickers=sorted({m.ticker for m in members if m.active})
    log.info("V3 universe: %s tickers",len(tickers))
    all_cf=fetch_universe(tickers)
    ranked=rank_v3(all_cf)
    out=Path("output"); out.mkdir(exist_ok=True)
    excel=out/f"egx_weekly_v3_report_{date.today().isoformat()}.xlsx"
    history=append_snapshot(ranked)
    build_excel_v3(ranked,str(excel),str(history),"data/universe_history.csv")
    if not excel.exists() or excel.stat().st_size==0: raise FileNotFoundError(str(excel))
    usable=sum(r.get("opportunity_score") is not None for r in ranked)
    send_document(str(excel),caption=f"EGX Weekly V3 Fundamental Research — {date.today():%d %b %Y} ({usable}/{len(ranked)} scored)")
    send_messages(build_report(ranked,top_n=10))
    log.info("V3 complete: %s",excel)
if __name__=="__main__": main()
