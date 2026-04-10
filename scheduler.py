#!/usr/bin/env python3
"""
=============================================================================
SCHEDULER - nano-pmu
=============================================================================
Tâches cron quotidiennes:
  12h00 → pmu_scraper.run()      Collecte données PMU
  12h30 → pmu_analyser.run()     Analyse multi-critères
  13h00 → pmu_publisher.run()    Git push → Vercel
          pmu_telegram.send_pronostics()   Envoi Telegram
  20h00 → pmu_resultats.run()    Résultats + bankroll
          pmu_telegram.send_bilan()         Bilan Telegram
=============================================================================
"""

import schedule
import time
import traceback
from datetime import datetime


def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")


def safe_run(fn, name):
    """Exécute une fonction en capturant les erreurs."""
    try:
        log(f"→ START {name}")
        fn()
        log(f"✓ OK    {name}")
    except Exception as e:
        log(f"✗ ERROR {name}: {e}")
        traceback.print_exc()
        # Alerte Telegram si possible
        try:
            from skills import pmu_telegram
            pmu_telegram.send_alert(f"Erreur dans {name}:\n{e}")
        except Exception:
            pass


# ============================================================================
# TACHES PLANIFIEES
# ============================================================================

def job_scraping():
    from skills import pmu_scraper
    safe_run(pmu_scraper.run, "pmu_scraper")


def job_analyse():
    from skills import pmu_analyser
    safe_run(pmu_analyser.run, "pmu_analyser")


def job_publication():
    from skills import pmu_publisher, pmu_telegram
    safe_run(pmu_publisher.run, "pmu_publisher")
    safe_run(pmu_telegram.send_pronostics, "telegram:pronostics")


def job_resultats():
    from skills import pmu_resultats, pmu_telegram
    safe_run(pmu_resultats.run, "pmu_resultats")
    safe_run(pmu_telegram.send_bilan, "telegram:bilan")


# ============================================================================
# CONFIGURATION DU SCHEDULER
# ============================================================================

def setup_schedule():
    schedule.every().day.at("12:00").do(job_scraping)
    schedule.every().day.at("12:30").do(job_analyse)
    schedule.every().day.at("13:00").do(job_publication)
    schedule.every().day.at("20:00").do(job_resultats)

    log("Scheduler configuré:")
    log("  12h00 → Scraping PMU")
    log("  12h30 → Analyse multi-critères")
    log("  13h00 → Publication + Telegram pronostics")
    log("  20h00 → Résultats + Telegram bilan")


def run_scheduler():
    """Lance la boucle principale du scheduler."""
    setup_schedule()
    log("Scheduler démarré — en attente des prochaines tâches...")

    while True:
        schedule.run_pending()
        time.sleep(30)  # Vérifier toutes les 30 secondes


if __name__ == "__main__":
    run_scheduler()
