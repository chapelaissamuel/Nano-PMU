#!/usr/bin/env python3
"""
=============================================================================
SKILL 4: RESULTATS DU JOUR (pmu_resultats.py)
=============================================================================
BUT: Récupérer les résultats des courses et calculer le bilan
EXECUTION: Chaque jour à 20h00 (via scheduler.py)

DONNEES COLLECTEES (depuis API PMU):
- Ordre d'arrivée de chaque course (via participants.ordreArrivee)
- Rapports définitifs (cotes finales, dividendes)
- Comparaison avec les pronostics générés

CALCULS:
- Mise totale / Gains / Pertes
- ROI (Return On Investment)
- Mise à jour bankroll persistante
=============================================================================
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime

# ============================================================================
# CONFIGURATION
# ============================================================================

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SKILL_DIR)
DATA_DIR = os.path.join(PROJECT_DIR, "data")
MEMORY_DIR = os.path.join(PROJECT_DIR, "memory")
BANKROLL_FILE = os.path.join(MEMORY_DIR, "bankroll.json")

PMU_OFFLINE_BASE = "https://offline.turfinfo.api.pmu.fr/rest/client/7/programme"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

REQUEST_DELAY = 0.5


# ============================================================================
# HELPERS
# ============================================================================

def pmu_date(dt=None):
    if dt is None:
        dt = datetime.now()
    return dt.strftime("%d%m%Y")


def file_date(dt=None):
    if dt is None:
        dt = datetime.now()
    return dt.strftime("%Y-%m-%d")


def api_get(url, retries=3):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            resp = urllib.request.urlopen(req, timeout=15)
            if resp.status == 204:
                return None
            return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code in (204, 404, 400):
                return None
            print(f"  [WARN] HTTP {e.code} pour {url} (tentative {attempt+1}/{retries})")
        except Exception as e:
            print(f"  [WARN] Erreur {e} (tentative {attempt+1}/{retries})")
        if attempt < retries - 1:
            time.sleep(1)
    return None


# ============================================================================
# RÉCUPÉRATION DES RÉSULTATS PMU
# ============================================================================

def get_course_results(pmu_date_str, reunion_num, course_num):
    """
    Récupère les résultats d'une course:
    - Participants avec ordreArrivee
    - Rapports définitifs (dividendes)
    """
    url_part = f"{PMU_OFFLINE_BASE}/{pmu_date_str}/R{reunion_num}/C{course_num}/participants"
    data_part = api_get(url_part)

    if not data_part:
        return None

    participants = data_part.get("participants", [])

    arrivee = []
    partants_detail = []
    for p in participants:
        ordre = p.get("ordreArrivee")
        cote_info = p.get("dernierRapportDirect", {})

        detail = {
            "numero": p.get("numPmu"),
            "cheval": p.get("nom", "?"),
            "ordreArrivee": ordre,
            "cote_finale": cote_info.get("rapport"),
            "statut": p.get("statut", ""),
        }
        partants_detail.append(detail)

        if ordre is not None and isinstance(ordre, int) and ordre > 0:
            arrivee.append((ordre, p.get("numPmu"), p.get("nom", "?")))

    arrivee.sort(key=lambda x: x[0])

    # Rapports définitifs
    url_rap = f"{PMU_OFFLINE_BASE}/{pmu_date_str}/R{reunion_num}/C{course_num}/rapports-definitifs"
    data_rap = api_get(url_rap)

    rapports = {}
    if data_rap and isinstance(data_rap, list):
        for r in data_rap:
            type_pari = r.get("typePari", "")
            raps = r.get("rapports", [])
            rapports[type_pari] = []
            for rap in raps:
                rapports[type_pari].append({
                    "combinaison": rap.get("combinaison", ""),
                    "dividende": rap.get("dividendePourUnEuro", 0),
                })

    rapport_gagnant = None
    if "SIMPLE_GAGNANT" in rapports and rapports["SIMPLE_GAGNANT"]:
        rapport_gagnant = rapports["SIMPLE_GAGNANT"][0].get("dividende", 0) / 100

    return {
        "arrivee": [a[1] for a in arrivee],
        "arrivee_detail": [{"place": a[0], "numero": a[1], "cheval": a[2]} for a in arrivee],
        "vainqueur": arrivee[0][2] if arrivee else None,
        "vainqueur_numero": arrivee[0][1] if arrivee else None,
        "cote_gagnant": rapport_gagnant,
        "rapports": rapports,
        "partants": partants_detail,
    }


def get_all_results(pmu_date_str=None):
    """
    Récupère les résultats de toutes les courses du jour.
    """
    print("[RESULTATS] Récupération des résultats PMU...")

    today = file_date()
    if pmu_date_str is None:
        pmu_date_str = pmu_date()

    programme_file = os.path.join(DATA_DIR, f"programme_{today}.json")
    if not os.path.exists(programme_file):
        print(f"[ERREUR] Fichier programme introuvable: {programme_file}")
        return None

    with open(programme_file, "r", encoding="utf-8") as f:
        programme = json.load(f)

    results = {
        "date": today,
        "pmu_date": pmu_date_str,
        "retrieved_at": datetime.now().isoformat(),
        "courses": [],
    }

    for reunion in programme.get("reunions", []):
        r_num = reunion["numExterne"]
        for course in reunion.get("courses", []):
            c_num = course["numero"]
            course_id = course["id"]

            result = get_course_results(pmu_date_str, r_num, c_num)
            if result and result["arrivee"]:
                result["id"] = course_id
                result["nom"] = course.get("nom", "")
                result["hippodrome"] = reunion.get("hippodrome", "")
                results["courses"].append(result)
                vainqueur = result.get("vainqueur", "?")
                cote = result.get("cote_gagnant", "?")
                print(f"  [OK] {course_id}: 1er={vainqueur} (cote {cote})")
            else:
                print(f"  [--] {course_id}: pas encore de résultat")

            time.sleep(REQUEST_DELAY)

    print(f"[RESULTATS] {len(results['courses'])} courses avec résultats")
    return results


# ============================================================================
# CALCUL DU BILAN
# ============================================================================

def load_pronostics():
    """Charge les pronostics du jour."""
    today = file_date()
    prono_file = os.path.join(DATA_DIR, f"pronostics_{today}.json")
    if os.path.exists(prono_file):
        with open(prono_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"courses": []}


def calculate_bilan(results, pronostics):
    """Compare les résultats réels avec les pronostics pour calculer le bilan."""
    print("[BILAN] Calcul du bilan...")

    bilan = {
        "date": results["date"],
        "courses_jouees": 0,
        "gagnes": 0,
        "perdues": 0,
        "mise_totale": 0,
        "gain_total": 0,
        "profit": 0,
        "roi": 0,
        "details": [],
    }

    for course_result in results.get("courses", []):
        course_id = course_result["id"]
        arrivee = course_result.get("arrivee", [])

        if not arrivee:
            continue

        prono_course = None
        for p in pronostics.get("courses", []):
            if p["id"] == course_id:
                prono_course = p
                break

        if not prono_course or not prono_course.get("pronostics"):
            continue

        bilan["courses_jouees"] += 1

        mise = prono_course.get("mise_totale", 0)
        bilan["mise_totale"] += mise

        top_horse = prono_course["pronostics"][0]
        top_numero = top_horse.get("numero", 0)

        if top_numero in arrivee[:3]:
            cote_reelle = course_result.get("cote_gagnant") or top_horse.get("cote", 1)
            gain = mise * cote_reelle
            bilan["gain_total"] += round(gain, 2)
            bilan["gagnes"] += 1
            resultat = "GAGNE"
        else:
            bilan["perdues"] += 1
            resultat = "PERDU"

        bilan["details"].append({
            "course": course_id,
            "hippodrome": course_result.get("hippodrome", ""),
            "nom": course_result.get("nom", ""),
            "arrivee": arrivee[:5],
            "vainqueur": course_result.get("vainqueur", "?"),
            "pronostic": top_horse.get("cheval", "N/A"),
            "pronostic_numero": top_numero,
            "mise": mise,
            "resultat": resultat,
        })

    bilan["profit"] = round(bilan["gain_total"] - bilan["mise_totale"], 2)
    if bilan["mise_totale"] > 0:
        bilan["roi"] = round((bilan["profit"] / bilan["mise_totale"]) * 100, 1)

    return bilan


def update_bankroll(bilan):
    """Met à jour le fichier bankroll avec le bilan du jour."""
    print("[BANKROLL] Mise à jour...")
    os.makedirs(MEMORY_DIR, exist_ok=True)

    bankroll = {
        "initial": 100,
        "current": 100,
        "history": [],
    }

    if os.path.exists(BANKROLL_FILE):
        with open(BANKROLL_FILE, "r", encoding="utf-8") as f:
            bankroll = json.load(f)

    # Vérifier si le bilan du jour existe déjà
    for entry in bankroll["history"]:
        if entry.get("date") == bilan["date"]:
            print(f"[BANKROLL] Bilan du {bilan['date']} déjà enregistré, mise à jour")
            bankroll["history"].remove(entry)
            bankroll["current"] -= entry.get("profit", 0)
            break

    bankroll["history"].append({
        "date": bilan["date"],
        "courses": bilan["courses_jouees"],
        "gagnes": bilan["gagnes"],
        "perdues": bilan["perdues"],
        "mise": bilan["mise_totale"],
        "gain": bilan["gain_total"],
        "profit": bilan["profit"],
        "roi": bilan["roi"],
        "bankroll_after": round(bankroll["current"] + bilan["profit"], 2),
    })

    bankroll["current"] = round(bankroll["current"] + bilan["profit"], 2)

    with open(BANKROLL_FILE, "w", encoding="utf-8") as f:
        json.dump(bankroll, f, ensure_ascii=False, indent=2)

    print(f"[OK] Bankroll: {bankroll['current']}€")
    return bankroll


# ============================================================================
# FONCTION PRINCIPALE
# ============================================================================

def get_daily_results():
    """Exécute la récupération complète des résultats."""
    print("=" * 60)
    print("RECUPERATION RESULTATS - Daily Racing Hub")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    results = get_all_results()
    if not results:
        print("[ERREUR] Impossible de récupérer les résultats")
        return None, None

    today = file_date()
    results_file = os.path.join(DATA_DIR, f"resultats_{today}.json")
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"[OK] Résultats sauvegardés: {results_file}")

    pronostics = load_pronostics()
    bilan = calculate_bilan(results, pronostics)

    bilan_file = os.path.join(DATA_DIR, f"bilan_{today}.json")
    with open(bilan_file, "w", encoding="utf-8") as f:
        json.dump(bilan, f, ensure_ascii=False, indent=2)
    print(f"[OK] Bilan sauvegardé: {bilan_file}")

    bankroll = update_bankroll(bilan)

    print()
    print("=" * 60)
    print("BILAN DU JOUR")
    print("=" * 60)
    print(f"Date:            {bilan['date']}")
    print(f"Courses jouées:  {bilan['courses_jouees']}")
    print(f"Gagnées:         {bilan['gagnes']} | Perdues: {bilan['perdues']}")
    print(f"Mise:            {bilan['mise_totale']}€ | Gains: {bilan['gain_total']}€")
    print(f"Profit:          {bilan['profit']}€ | ROI: {bilan['roi']}%")
    print(f"Bankroll actuel: {bankroll['current']}€")
    print("=" * 60)

    return bilan, bankroll


def run():
    """Point d'entrée appelé par le scheduler."""
    return get_daily_results()


if __name__ == "__main__":
    get_daily_results()
