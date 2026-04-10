#!/usr/bin/env python3
"""
=============================================================================
SKILL 2: ANALYSE MULTI-CRITERES (pmu_analyser.py)
=============================================================================
BUT: Générer les pronostics automatiquement basés sur les données collectées
EXECUTION: Chaque jour à 12h30 (via scheduler.py, après scraping)

CRITERES DE SCORING:
- Cote et valeur (value bet detection)    : 0-4 pts
- Musique (résultats récents codifiés)    : 0-5 pts
- Taux victoires/places en carrière       : 0-4 pts
- Gains en carrière et année en cours     : 0-3 pts
- Performances détaillées (5 dernières)  : 0-4 pts
=============================================================================
"""

import json
import os
import re
import sys
from datetime import datetime
from collections import defaultdict

# ============================================================================
# CONFIGURATION
# ============================================================================

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SKILL_DIR)
DATA_DIR = os.path.join(PROJECT_DIR, "data")


# ============================================================================
# CHARGEMENT DES DONNEES
# ============================================================================

def load_data():
    """Charge les données du scraping précédent."""
    print("[DATA] Chargement des données...")
    today = datetime.now().strftime("%Y-%m-%d")

    programme_file = os.path.join(DATA_DIR, f"programme_{today}.json")
    if not os.path.exists(programme_file):
        print(f"[ERREUR] Fichier programme introuvable: {programme_file}")
        return None, None, None

    with open(programme_file, "r", encoding="utf-8") as f:
        programme = json.load(f)

    cotes_file = os.path.join(DATA_DIR, f"cotes_{today}.json")
    cotes = {}
    if os.path.exists(cotes_file):
        with open(cotes_file, "r", encoding="utf-8") as f:
            cotes_data = json.load(f)
            cotes = cotes_data.get("courses", {})

    perfs_file = os.path.join(DATA_DIR, f"performances_{today}.json")
    perfs = {}
    if os.path.exists(perfs_file):
        with open(perfs_file, "r", encoding="utf-8") as f:
            perfs = json.load(f)

    print(f"[DATA] Programme: {len(programme.get('reunions', []))} réunions")
    print(f"[DATA] Cotes: {len(cotes)} courses")
    print(f"[DATA] Performances: {len(perfs)} courses")

    return programme, cotes, perfs


# ============================================================================
# PARSING DE LA MUSIQUE
# ============================================================================

def parse_musique(musique):
    """
    Parse la musique PMU (ex: '1m3m(25)0m7mDm6m2m5m8m').
    Retourne une liste de résultats récents (plus récent en premier).

    Codes:
    - Chiffre (1-9): place obtenue
    - 0: non classé (10e et au-delà)
    - D: disqualifié / A: arrêté / T: tombé
    - Lettre après chiffre: discipline (m=monté, a=attelé, p=plat, h=haies)
    - (25): retour de repos (25 jours)
    """
    if not musique:
        return []

    results = []
    pattern = r'(\d|D|A|T|Ret)([a-z])?'
    clean = re.sub(r'\([^)]*\)', '', musique)
    matches = re.findall(pattern, clean, re.IGNORECASE)

    for place, discipline in matches:
        if place.isdigit():
            results.append(int(place))
        elif place.upper() == 'D':
            results.append(99)
        elif place.upper() == 'A':
            results.append(98)
        elif place.upper() == 'T':
            results.append(97)
        else:
            results.append(99)

    return results


# ============================================================================
# SCORING DES CHEVAUX
# ============================================================================

def analyze_horse(horse, course_data, perfs_data=None):
    """
    Analyse un cheval et retourne un score de confiance.

    Score basé sur plusieurs critères pondérés:
    - Cote (value bet)          : 0-4 pts
    - Musique (forme récente)   : 0-5 pts
    - Stats carrière            : 0-4 pts
    - Gains                     : 0-3 pts
    - Performances détaillées   : 0-4 pts
    """
    score = 0
    reasons = []
    cote = horse.get("cote")
    distance = course_data.get("distance", 2000)
    nb_partants = course_data.get("partants", 10)

    # ---- 1. ANALYSE DE LA COTE (0-4 pts) ----
    if cote is not None:
        if cote <= 2.5:
            score += 4
            reasons.append(f"Grand favori (cote {cote})")
        elif cote <= 4:
            score += 3
            reasons.append(f"Favori solide (cote {cote})")
        elif cote <= 7:
            score += 2
            reasons.append(f"Cote intéressante ({cote})")
        elif cote <= 12:
            score += 1
            reasons.append(f"Second choix (cote {cote})")

    # ---- 2. MUSIQUE / FORME RECENTE (0-5 pts) ----
    musique = parse_musique(horse.get("musique", ""))
    if musique:
        recent = musique[:3]
        for place in recent:
            if place == 1:
                score += 2
                reasons.append("Victoire récente")
            elif place <= 3:
                score += 1
                reasons.append(f"Placé récemment ({place}e)")

        last5 = musique[:5]
        if last5 and all(p <= 5 for p in last5):
            score += 1
            reasons.append("Très régulier (top 5 systématique)")

    # ---- 3. STATS CARRIERE (0-4 pts) ----
    nb_courses = horse.get("nombreCourses", 0)
    nb_victoires = horse.get("nombreVictoires", 0)
    nb_places = horse.get("nombrePlaces", 0)

    if nb_courses > 0:
        taux_victoire = nb_victoires / nb_courses
        taux_place = nb_places / nb_courses

        if taux_victoire >= 0.25:
            score += 2
            reasons.append(f"Excellent taux victoire ({taux_victoire:.0%})")
        elif taux_victoire >= 0.15:
            score += 1
            reasons.append(f"Bon taux victoire ({taux_victoire:.0%})")

        if taux_place >= 0.50:
            score += 2
            reasons.append(f"Très souvent placé ({taux_place:.0%})")
        elif taux_place >= 0.35:
            score += 1
            reasons.append(f"Régulièrement placé ({taux_place:.0%})")

    # ---- 4. GAINS (0-3 pts) ----
    gains_carriere = horse.get("gainsCarriere", 0) / 100
    gains_annee = horse.get("gainsAnnee", 0) / 100

    if gains_carriere > 200000:
        score += 2
        reasons.append("Gros gains carrière")
    elif gains_carriere > 80000:
        score += 1
        reasons.append("Gains carrière honorables")

    if gains_annee > 30000:
        score += 1
        reasons.append("En forme cette année (gains)")

    # ---- 5. PERFORMANCES DETAILLEES (0-4 pts) ----
    if perfs_data:
        num = horse.get("numero")
        horse_perfs = perfs_data.get(str(num), {})
        historique = horse_perfs.get("historique", [])

        if historique:
            places_top3 = sum(1 for h in historique if h.get("place") and h["place"] <= 3)

            if places_top3 >= 4:
                score += 3
                reasons.append(f"Excellent historique ({places_top3}/5 top 3)")
            elif places_top3 >= 3:
                score += 2
                reasons.append(f"Bon historique ({places_top3}/5 top 3)")
            elif places_top3 >= 2:
                score += 1
                reasons.append(f"Historique correct ({places_top3}/5 top 3)")

            for h in historique:
                h_dist = h.get("distance", 0)
                if h_dist and abs(h_dist - distance) <= 200 and h.get("place") and h["place"] <= 2:
                    score += 1
                    reasons.append(f"Performant sur ~{distance}m")
                    break

    # ---- MALUS ----
    if horse.get("statut") != "PARTANT":
        score = 0
        reasons = ["NON PARTANT"]

    max_possible = 20
    confidence = min(5, max(1, round((score / max_possible) * 5)))

    return {
        "score": score,
        "confidence": confidence,
        "reasons": reasons,
    }


# ============================================================================
# GENERATION DES PRONOSTICS
# ============================================================================

def generate_pronostics(programme, cotes, perfs):
    """Génère les pronostics pour toutes les courses du jour."""
    print("[ANALYSE] Génération des pronostics...")

    today = datetime.now().strftime("%Y-%m-%d")
    pronostics = {
        "date": today,
        "generated_at": datetime.now().isoformat(),
        "courses": [],
    }

    for reunion in programme.get("reunions", []):
        for course in reunion.get("courses", []):
            course_id = course["id"]

            course_partants = cotes.get(course_id, [])
            if not course_partants:
                continue

            course_perfs = perfs.get(course_id, {})

            analyzed = []
            for horse in course_partants:
                analysis = analyze_horse(horse, course, course_perfs)
                analyzed.append({
                    "numero": horse["numero"],
                    "cheval": horse["cheval"],
                    "cote": horse.get("cote"),
                    "musique": horse.get("musique", ""),
                    "driver": horse.get("driver", ""),
                    "entraineur": horse.get("entraineur", ""),
                    "score": analysis["score"],
                    "confidence": analysis["confidence"],
                    "reasons": analysis["reasons"],
                })

            analyzed.sort(key=lambda x: x["score"], reverse=True)

            top_score = analyzed[0]["score"] if analyzed else 0
            second_score = analyzed[1]["score"] if len(analyzed) > 1 else 0
            ecart = top_score - second_score

            if top_score >= 10 and ecart >= 3:
                risk = "LOW"
            elif top_score >= 6:
                risk = "MEDIUM"
            else:
                risk = "HIGH"

            prono = {
                "id": course_id,
                "nom": course.get("nom", ""),
                "hippodrome": reunion.get("hippodrome", ""),
                "pays": reunion.get("pays", ""),
                "heure": course.get("heure", ""),
                "distance": course.get("distance", 0),
                "discipline": course.get("discipline", ""),
                "specialite": course.get("specialite", ""),
                "partants_count": len(course_partants),
                "risk": risk,
                "pronostics": analyzed[:5],
                "mise_totale": len(analyzed[:3]),
            }

            pronostics["courses"].append(prono)
            print(f"  [OK] {course_id} ({reunion['hippodrome']}): "
                  f"top={analyzed[0]['cheval'] if analyzed else '?'} "
                  f"score={top_score} risk={risk}")

    return pronostics


def generate_risk_list(pronostics):
    """Génère la risk list (courses recommandées pour parier)."""
    print("[RISK] Génération de la risk list...")

    low_risk = [c for c in pronostics["courses"] if c["risk"] == "LOW"]
    medium_risk = [c for c in pronostics["courses"] if c["risk"] == "MEDIUM"]
    high_risk = [c for c in pronostics["courses"] if c["risk"] == "HIGH"]

    risk_list = {
        "date": pronostics["date"],
        "generated_at": pronostics["generated_at"],
        "recommended": low_risk,
        "caution": medium_risk,
        "avoid": high_risk,
        "total_recommended": len(low_risk),
        "total_courses": len(pronostics["courses"]),
        "mise_totale": sum(c["mise_totale"] for c in low_risk),
    }

    return risk_list


# ============================================================================
# FONCTION PRINCIPALE
# ============================================================================

def run_analysis():
    """Exécute l'analyse complète."""
    print("=" * 60)
    print("DEMARRAGE ANALYSE - Daily Racing Hub")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    programme, cotes, perfs = load_data()
    if programme is None:
        print("[ERREUR] Pas de données disponibles")
        return None, None

    pronostics = generate_pronostics(programme, cotes, perfs)

    today = datetime.now().strftime("%Y-%m-%d")
    prono_file = os.path.join(DATA_DIR, f"pronostics_{today}.json")
    with open(prono_file, "w", encoding="utf-8") as f:
        json.dump(pronostics, f, ensure_ascii=False, indent=2)
    print(f"[OK] Pronostics sauvegardés: {prono_file}")

    risk_list = generate_risk_list(pronostics)

    risk_file = os.path.join(DATA_DIR, f"risklist_{today}.json")
    with open(risk_file, "w", encoding="utf-8") as f:
        json.dump(risk_list, f, ensure_ascii=False, indent=2)
    print(f"[OK] Risk list sauvegardée: {risk_file}")

    print()
    print("=" * 60)
    print("RESUME DES PRONOSTICS")
    print("=" * 60)
    print(f"Date:          {pronostics['date']}")
    print(f"Courses:       {len(pronostics['courses'])}")
    print(f"Recommandées:  {risk_list['total_recommended']} (LOW risk)")
    print(f"Prudence:      {len(risk_list['caution'])} (MEDIUM risk)")
    print(f"A éviter:      {len(risk_list['avoid'])} (HIGH risk)")
    print(f"Mise totale:   {risk_list['mise_totale']}€")
    print("=" * 60)

    return pronostics, risk_list


def run():
    """Point d'entrée appelé par le scheduler."""
    return run_analysis()


if __name__ == "__main__":
    run_analysis()
