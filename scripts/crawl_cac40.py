"""
Batch crawl all CAC 40 companies with rate-limit-safe delays.

Usage:
    python scripts/crawl_cac40.py
    python scripts/crawl_cac40.py --delay 5        # slower, safer
    python scripts/crawl_cac40.py --skip-existing  # only new tickers
"""
from __future__ import annotations
import sys, argparse, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

CAC40 = [
    ("AIR.PA",  "Airbus"),
    ("AI.PA",   "Air Liquide"),
    ("ALO.PA",  "Alstom"),
    ("MT.AS",   "ArcelorMittal"),
    ("CS.PA",   "AXA"),
    ("BNP.PA",  "BNP Paribas"),
    ("EN.PA",   "Bouygues"),
    ("CAP.PA",  "Capgemini"),
    ("CA.PA",   "Carrefour"),
    ("ACA.PA",  "Crédit Agricole"),
    ("BN.PA",   "Danone"),
    ("DSY.PA",  "Dassault Systèmes"),
    ("ENGI.PA", "Engie"),
    ("EL.PA",   "EssilorLuxottica"),
    ("RMS.PA",  "Hermès"),
    ("KER.PA",  "Kering"),
    ("LR.PA",   "Legrand"),
    ("LVMH.PA", "LVMH"),
    ("OR.PA",   "L'Oréal"),
    ("ML.PA",   "Michelin"),
    ("ORA.PA",  "Orange"),
    ("RI.PA",   "Pernod Ricard"),
    ("PUB.PA",  "Publicis"),
    ("RNO.PA",  "Renault"),
    ("SAF.PA",  "Safran"),
    ("SGO.PA",  "Saint-Gobain"),
    ("SAN.PA",  "Sanofi"),
    ("GLE.PA",  "Société Générale"),
    ("STM",     "STMicroelectronics"),
    ("TEP.PA",  "Teleperformance"),
    ("HO.PA",   "Thales"),
    ("TTE.PA",  "TotalEnergies"),
    ("URW.AS",  "Unibail-Rodamco"),
    ("VIE.PA",  "Veolia"),
    ("DG.PA",   "Vinci"),
    ("VIV.PA",  "Vivendi"),
    ("WLN.PA",  "Worldline"),
    ("SU.PA",   "Schneider Electric"),
    ("SW.PA",   "Sodexo"),
    ("MC.PA",   "LVMH (alt)"),  # secondary listing check
]


def crawl_all(delay: float = 2.0, skip_existing: bool = False) -> None:
    from src.db.models import init_db, SessionLocal, Company
    from scripts.crawl_company import crawl

    init_db()
    existing: set[str] = set()
    if skip_existing:
        s = SessionLocal()
        existing = {c.ticker for c in s.query(Company).all()}
        s.close()
        print(f"Skipping {len(existing)} already-crawled tickers.\n")

    total = len(CAC40)
    success, failed = 0, []

    for i, (ticker, name) in enumerate(CAC40, start=1):
        if skip_existing and ticker in existing:
            print(f"[{i}/{total}] SKIP {name} ({ticker})")
            continue
        print(f"\n[{i}/{total}] {name} ({ticker})")
        try:
            crawl(ticker, name)
            success += 1
        except Exception as e:
            print(f"  ERROR: {e}")
            failed.append((ticker, name, str(e)))
        if i < total:
            time.sleep(delay)

    print(f"\n{'='*50}")
    print(f"Done: {success} succeeded, {len(failed)} failed")
    if failed:
        print("Failed tickers:")
        for t, n, e in failed:
            print(f"  {t} ({n}): {e}")
    print("\nNext step: git add data/processed/valuation_lab.db && git commit -m 'Refresh CAC40' && git push")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--delay",         type=float, default=2.0)
    parser.add_argument("--skip-existing", action="store_true")
    args = parser.parse_args()
    crawl_all(args.delay, args.skip_existing)
