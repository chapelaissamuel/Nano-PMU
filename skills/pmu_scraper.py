#!/usr/bin/env python3
"""
=============================================================================
SKILL 1: SCRAPING AUTOMATIQUE (pmu_scraper.py)
=============================================================================
BUT: Collecter les données des courses hippiques depuis l'API PMU
EXECUTION: Chaque jour à 12h00 (via scheduler.py)

DONNEES COLLECTEES:
- Programme du jour (reunions, courses, horaires)
- Participants et cotes de chaque course
- Historique des performances des chevaux (5 dernières courses)

SOURCE DE DONNEES:
- offline.turfinfo.api.pmu.fr : programme, participants, rapports
- online.turfinfo.api.pmu.fr  : performances détaillées
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

PMU_OFFLINE_BASE = "https://offline.turfinfo.api.pmu.fr/rest/client/7/programme"
PMU_ONLINE_BASE = "https://online.turfinfo.api.pmu.fr/rest/client/61/programme"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

REQUEST_DELAY = 0.5


# ============================================================================
# HELPERS
# ============================================================================

def pmu_date(dt=None):
    """Formate une date au format PMU (DDMMYYYY)."""
    if dt is None:
        dt = datetime.now()
    return dt.strftime("%d%m%Y")


def file_date(dt=None):
    """Formate une date pour les noms de fichiers (YYYY-MM-DD)."""
    if dt is None:
        dt = datetime.now()
    return dt.strftime("%Y-%m-%d")


def timestamp_to_time(ts):
    """Convertit un timestamp PMU (ms) en heure lisible HH:MM."""
    if not ts:
        return "?"
    try:
        return datetime.fromtimestamp(ts / 1000).strftime("%Hh%M")
    except (OSError, ValueError):
        return "?"


def api_get(url, retries=3):
    """Effectue un GET sur l'API PMU avec retry."""
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            resp = urllib.request.urlopen(req, timeout=15)
            if resp.status == 204:
                return None
            return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 204:
                return None
            if e.code in (404, 400):
                return None
            print(f"  [WARN] HTTP {e.code} pour {url} (tentative {attempt+1}/{retries})")
        except Exception as e:
            print(f"  [WARN] Erreur {e} pour {url} (tentative {attempt+1}/{retries})")
        if attempt < retries - 1:
            time.sleep(1)
    return None


# ============================================================================
# SCRAPING DU PROGRAMME
# ============================================================================

def get_programme(date_str=None):
    """
    Récupère le programme complet du jour depuis l'API PMU offline.
    Retourne la structure programme avec toutes les réunions et courses.
    """
    d = pmu_date() if date_str is None else date_str
    print(f"[PMU] Récupération du programme ({d})...")

    url = f"{PMU_OFFLINE_BASE}/{d}"
    data = api_get(url)

    if not data or "programme" not in data:
        print("[PMU] Aucun programme trouvé")
        return None

    raw = data["programme"]
    reunions_raw = raw.get("reunions", [])
    print(f"[PMU] {len(reunions_raw)} réunions trouvées")

    programme = {
        "date": file_date(),
        "pmu_date": d,
        "reunions": [],
    }

    for r in reunions_raw:
        hippodrome = r.get("hippodrome", {})
        pays = r.get("pays", {})
        courses_raw = r.get("courses", [])

        reunion = {
            "id": f"R{r['numExterne']}",
            "numOfficiel": r.get("numOfficiel"),
            "numExterne": r.get("numExterne"),
            "hippodrome": hippodrome.get("libelleCourt", "?"),
            "hippodrome_long": hippodrome.get("libelleLong", ""),
            "code_hippodrome": hippodrome.get("code", ""),
            "pays": pays.get("libelle", ""),
            "pays_code": pays.get("code", ""),
            "nature": r.get("nature", ""),
            "nombreCourses": len(courses_raw),
            "courses": [],
        }

        for c in courses_raw:
            paris_types = [p.get("typePari", "") for p in c.get("paris", []) if p.get("enVente")]

            course = {
                "id": f"R{r['numExterne']}C{c['numExterne']}",
                "numero": c.get("numExterne"),
                "numOrdre": c.get("numOrdre"),
                "nom": c.get("libelle", ""),
                "nom_court": c.get("libelleCourt", ""),
                "heure": timestamp_to_time(c.get("heureDepart")),
                "heureDepart_ts": c.get("heureDepart"),
                "distance": c.get("distance", 0),
                "distanceUnit": c.get("distanceUnit", "METRE"),
                "discipline": c.get("discipline", ""),
                "specialite": c.get("specialite", ""),
                "parcours": c.get("parcours", ""),
                "corde": c.get("corde", ""),
                "partants": c.get("nombreDeclaresPartants", 0),
                "montantPrix": c.get("montantPrix", 0),
                "montantOffert1er": c.get("montantOffert1er", 0),
                "conditions": c.get("conditions", ""),
                "conditionSexe": c.get("conditionSexe", ""),
                "categorieParticularite": c.get("categorieParticularite", ""),
                "paris_disponibles": paris_types,
                "status": "upcoming",
            }

            reunion["courses"].append(course)

        programme["reunions"].append(reunion)

    return programme


# ============================================================================
# SCRAPING DES PARTICIPANTS ET COTES
# ============================================================================

def get_participants(pmu_date_str, reunion_num, course_num):
    """
    Récupère les participants (chevaux) et leurs cotes pour une course.
    """
    url = f"{PMU_OFFLINE_BASE}/{pmu_date_str}/R{reunion_num}/C{course_num}/participants?specialisation=INTERNET"
    data = api_get(url)

    if not data:
        return []

    participants_raw = data.get("participants", [])
    participants = []

    for p in participants_raw:
        cote_direct = p.get("dernierRapportDirect", {})
        cote_ref = p.get("dernierRapportReference", {})
        gains = p.get("gainsParticipant", {})

        participant = {
            "numero": p.get("numPmu"),
            "cheval": p.get("nom", "?"),
            "age": p.get("age"),
            "sexe": p.get("sexe", ""),
            "race": p.get("race", ""),
            "statut": p.get("statut", ""),
            "driver": p.get("driver", ""),
            "entraineur": p.get("entraineur", ""),
            "proprietaire": p.get("proprietaire", ""),
            "musique": p.get("musique", ""),
            "nombreCourses": p.get("nombreCourses", 0),
            "nombreVictoires": p.get("nombreVictoires", 0),
            "nombrePlaces": p.get("nombrePlaces", 0),
            "nombrePlacesSecond": p.get("nombrePlacesSecond", 0),
            "nombrePlacesTroisieme": p.get("nombrePlacesTroisieme", 0),
            "cote": cote_direct.get("rapport"),
            "cote_tendance": cote_direct.get("indicateurTendance", ""),
            "cote_reference": cote_ref.get("rapport"),
            "favori": cote_direct.get("favoris", False),
            "gainsCarriere": gains.get("gainsCarriere", 0),
            "gainsAnnee": gains.get("gainsAnneeEnCours", 0),
            "nomPere": p.get("nomPere", ""),
            "nomMere": p.get("nomMere", ""),
            "handicapDistance": p.get("handicapDistance"),
            "handicapPoids": p.get("handicapPoids"),
            "deferre": p.get("deferre", ""),
            "oeilleres": p.get("oeilleres", ""),
        }

        participants.append(participant)

    return participants


def get_all_participants(programme):
    """
    Récupère les participants de toutes les courses du programme.
    Retourne un dict {course_id: [participants]}.
    """
    print("[PMU] Récupération des participants et cotes...")
    all_participants = {}
    total = 0

    for reunion in programme.get("reunions", []):
        r_num = reunion["numExterne"]
        for course in reunion.get("courses", []):
            c_num = course["numero"]
            course_id = course["id"]

            participants = get_participants(programme["pmu_date"], r_num, c_num)
            if participants:
                # Filtrer les non-partants
                partants = [p for p in participants if p["statut"] == "PARTANT"]
                all_participants[course_id] = partants
                total += len(partants)
                print(f"  [OK] {course_id}: {len(partants)} partants")
            else:
                all_participants[course_id] = []
                print(f"  [--] {course_id}: aucun participant")

            time.sleep(REQUEST_DELAY)

    print(f"[PMU] Total: {total} partants récupérés")
    return all_participants


# ============================================================================
# SCRAPING DES PERFORMANCES DETAILLEES
# ============================================================================

def get_performances(pmu_date_str, reunion_num, course_num):
    """
    Récupère les performances détaillées (5 dernières courses)
    de chaque cheval d'une course.
    """
    url = f"{PMU_ONLINE_BASE}/{pmu_date_str}/R{reunion_num}/C{course_num}/performances-detaillees/pretty"
    data = api_get(url)

    if not data:
        return {}

    perfs = {}
    for participant in data.get("participants", []):
        num = participant.get("numPmu")
        nom = participant.get("nomCheval", "?")
        courses = participant.get("coursesCourues", [])

        historique = []
        for course in courses:
            hippo = course.get("hippodrome", "?")
            dist = course.get("distance", 0)
            nb_part = course.get("nbParticipants", 0)
            alloc = course.get("allocation", 0)

            place = None
            for p in course.get("participants", []):
                if p.get("itsHim"):
                    place_info = p.get("place", {})
                    place = place_info.get("place")
                    break

            historique.append({
                "date_ts": course.get("date"),
                "hippodrome": hippo,
                "distance": dist,
                "discipline": course.get("discipline", ""),
                "nbParticipants": nb_part,
                "allocation": alloc,
                "place": place,
            })

        perfs[num] = {
            "nom": nom,
            "historique": historique,
        }

    return perfs


# ============================================================================
# FONCTION PRINCIPALE
# ============================================================================

def scrape_all(target_date=None):
    """
    Fonction principale: scrape tout le programme du jour.
    target_date: format DDMMYYYY (optionnel, défaut = aujourd'hui)
    """
    print("=" * 60)
    print(f"DEMARRAGE SCRAPING - Daily Racing Hub")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    os.makedirs(DATA_DIR, exist_ok=True)

    # 1. Récupérer le programme PMU
    programme = get_programme(target_date)
    if not programme:
        print("[ERREUR] Impossible de récupérer le programme")
        return False

    today = file_date()
    programme_file = os.path.join(DATA_DIR, f"programme_{today}.json")
    with open(programme_file, "w", encoding="utf-8") as f:
        json.dump(programme, f, ensure_ascii=False, indent=2)
    print(f"[OK] Programme sauvegardé: {programme_file}")

    total_courses = sum(len(r.get("courses", [])) for r in programme["reunions"])
    print(f"     {len(programme['reunions'])} réunions, {total_courses} courses")

    # 2. Récupérer les participants et cotes
    all_participants = get_all_participants(programme)

    cotes_file = os.path.join(DATA_DIR, f"cotes_{today}.json")
    cotes_data = {
        "date": today,
        "pmu_date": programme["pmu_date"],
        "mise_a_jour": datetime.now().isoformat(),
        "courses": all_participants,
    }
    with open(cotes_file, "w", encoding="utf-8") as f:
        json.dump(cotes_data, f, ensure_ascii=False, indent=2)
    print(f"[OK] Cotes sauvegardées: {cotes_file}")

    # 3. Récupérer les performances détaillées (courses françaises seulement)
    print("[PMU] Récupération des performances détaillées...")
    all_perfs = {}
    for reunion in programme.get("reunions", []):
        r_num = reunion["numExterne"]
        if reunion.get("pays_code") != "FRA":
            continue
        for course in reunion.get("courses", []):
            c_num = course["numero"]
            course_id = course["id"]
            perfs = get_performances(programme["pmu_date"], r_num, c_num)
            if perfs:
                all_perfs[course_id] = perfs
                print(f"  [OK] {course_id}: perfs de {len(perfs)} chevaux")
            time.sleep(REQUEST_DELAY)

    perfs_file = os.path.join(DATA_DIR, f"performances_{today}.json")
    with open(perfs_file, "w", encoding="utf-8") as f:
        json.dump(all_perfs, f, ensure_ascii=False, indent=2)
    print(f"[OK] Performances sauvegardées: {perfs_file}")

    # 4. Résumé
    resume = {
        "date": today,
        "reunions_count": len(programme["reunions"]),
        "courses_count": total_courses,
        "partants_count": sum(len(v) for v in all_participants.values()),
        "reunions": [
            {
                "id": r["id"],
                "hippodrome": r["hippodrome"],
                "pays": r["pays"],
                "courses": len(r.get("courses", [])),
            }
            for r in programme["reunions"]
        ],
        "scraping_time": datetime.now().isoformat(),
        "pronostics_ready": False,
    }

    resume_file = os.path.join(DATA_DIR, "resume.json")
    with open(resume_file, "w", encoding="utf-8") as f:
        json.dump(resume, f, ensure_ascii=False, indent=2)

    print()
    print("=" * 60)
    print("SCRAPING TERMINE AVEC SUCCES")
    print(f"  Réunions: {len(programme['reunions'])}")
    print(f"  Courses:  {total_courses}")
    print(f"  Partants: {sum(len(v) for v in all_participants.values())}")
    print(f"  Perfs:    {sum(len(v) for v in all_perfs.values())} chevaux")
    print("=" * 60)

    return True


def run():
    """Point d'entrée appelé par le scheduler."""
    target = sys.argv[1] if len(sys.argv) > 1 else None
    return scrape_all(target)


if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
