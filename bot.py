#!/usr/bin/env python3
"""
=============================================================================
BOT.PY — Orchestrateur principal nano-pmu
=============================================================================
Point d'entrée du bot. Lance le scheduler et gère les commandes manuelles.

Utilisation:
  python bot.py                   # Lance le scheduler automatique
  python bot.py scrape            # Lance le scraping maintenant
  python bot.py analyse           # Lance l'analyse maintenant
  python bot.py publish           # Lance la publication maintenant
  python bot.py resultats         # Lance la récupération des résultats
  python bot.py pronostics        # Envoie les pronostics Telegram maintenant
  python bot.py bilan             # Envoie le bilan Telegram maintenant
  python bot.py all               # Exécute tout le pipeline maintenant
=============================================================================
"""

import sys
import os
import traceback
from datetime import datetime

# S'assurer que le dossier nano-pmu est dans le path Python
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")


def run_all():
    """Exécute le pipeline complet dans l'ordre."""
    log("=== PIPELINE COMPLET ===")

    from skills import pmu_scraper, pmu_analyser, pmu_publisher, pmu_resultats, pmu_telegram

    log("1/5 → Scraping...")
    pmu_scraper.run()

    log("2/5 → Analyse...")
    pmu_analyser.run()

    log("3/5 → Publication...")
    pmu_publisher.run()

    log("4/5 → Telegram pronostics...")
    pmu_telegram.send_pronostics()

    log("5/5 → Résultats...")
    pmu_resultats.run()

    log("=== PIPELINE TERMINE ===")


def main():
    # Charger les variables d'environnement
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
        log("Variables .env chargées")
    except ImportError:
        pass

    # Vérifier les secrets requis
    missing = []
    for var in ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]:
        if not os.environ.get(var):
            missing.append(var)
    if missing:
        log(f"[WARN] Variables manquantes: {', '.join(missing)}")
        log("[WARN] Les notifications Telegram seront désactivées")

    # Traiter les commandes manuelles
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()

        if cmd == "scrape":
            from skills import pmu_scraper
            pmu_scraper.run()

        elif cmd == "analyse":
            from skills import pmu_analyser
            pmu_analyser.run()

        elif cmd == "publish":
            from skills import pmu_publisher
            pmu_publisher.run()

        elif cmd == "resultats":
            from skills import pmu_resultats
            pmu_resultats.run()

        elif cmd == "pronostics":
            from skills import pmu_telegram
            pmu_telegram.send_pronostics()

        elif cmd == "bilan":
            from skills import pmu_telegram
            pmu_telegram.send_bilan()

        elif cmd == "all":
            run_all()

        else:
            print(f"Commande inconnue: {cmd}")
            print("Commandes: scrape | analyse | publish | resultats | pronostics | bilan | all")
            sys.exit(1)

    else:
        # Mode normal: lancer le scheduler
        from scheduler import run_scheduler
        run_scheduler()


if __name__ == "__main__":
    main()
