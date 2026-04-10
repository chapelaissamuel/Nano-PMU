#!/usr/bin/env python3
"""
=============================================================================
SKILL 3: PUBLICATION AUTOMATIQUE (pmu_publisher.py)
=============================================================================
BUT: Mettre à jour le site web automatiquement avec les nouveaux pronostics
EXECUTION: Chaque jour à 13h00 (via scheduler.py, après analyse)

METHODES DE PUBLICATION:
1. Génération de fichiers JSON pour le frontend Next.js
2. Push via GitHub API (déclenche Vercel) — fonctionne sans git local

FICHIERS GENERES:
- data/pronostics.json  -> Utilisé par /pronostics
- data/risklist.json    -> Utilisé par /today et hero
- data/programme.json   -> Utilisé par /programme
=============================================================================
"""

import json
import os
import sys
import base64
import urllib.request
import urllib.error
from datetime import datetime

# ============================================================================
# CONFIGURATION
# ============================================================================

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SKILL_DIR)
DATA_DIR = os.path.join(PROJECT_DIR, "data")

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "")  # ex: chapelaissamuel/Nano-PMU

GITHUB_API = "https://api.github.com"


# ============================================================================
# FONCTIONS
# ============================================================================

def load_latest_data():
    """Charge les derniers fichiers de données."""
    print("[LOAD] Chargement des données...")
    today = datetime.now().strftime("%Y-%m-%d")

    pronostics = {"courses": []}
    prono_file = os.path.join(DATA_DIR, f"pronostics_{today}.json")
    if os.path.exists(prono_file):
        with open(prono_file, "r", encoding="utf-8") as f:
            pronostics = json.load(f)
    else:
        print("[WARN] Pas de fichier pronostics")

    risklist = {"recommended": [], "caution": []}
    risk_file = os.path.join(DATA_DIR, f"risklist_{today}.json")
    if os.path.exists(risk_file):
        with open(risk_file, "r", encoding="utf-8") as f:
            risklist = json.load(f)

    programme = {"reunions": []}
    prog_file = os.path.join(DATA_DIR, f"programme_{today}.json")
    if os.path.exists(prog_file):
        with open(prog_file, "r", encoding="utf-8") as f:
            programme = json.load(f)

    return pronostics, risklist, programme


def generate_public_data(pronostics, risklist, programme):
    """Génère les fichiers JSON publics pour le site."""
    print("[GEN] Génération des fichiers publics...")

    now = datetime.now().isoformat()
    today = pronostics.get("date", datetime.now().strftime("%Y-%m-%d"))

    # 1. pronostics.json (pour /pronostics)
    public_pronostics = {
        "updated": now,
        "date": today,
        "courses": pronostics.get("courses", []),
    }
    out = os.path.join(DATA_DIR, "pronostics.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(public_pronostics, f, ensure_ascii=False, indent=2)
    print(f"  [OK] pronostics.json")

    # 2. risklist.json (pour /today et hero)
    public_risk = {
        "updated": now,
        "date": today,
        "recommended": risklist.get("recommended", []),
        "caution": risklist.get("caution", []),
        "total": risklist.get("total_recommended", 0),
        "total_courses": risklist.get("total_courses", 0),
        "mise_totale": risklist.get("mise_totale", 0),
    }
    out = os.path.join(DATA_DIR, "risklist.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(public_risk, f, ensure_ascii=False, indent=2)
    print(f"  [OK] risklist.json")

    # 3. programme.json (pour /programme)
    public_programme = {
        "updated": now,
        "date": today,
        "reunions": [
            {
                "id": r.get("id", ""),
                "hippodrome": r.get("hippodrome", ""),
                "hippodrome_long": r.get("hippodrome_long", ""),
                "pays": r.get("pays", ""),
                "nature": r.get("nature", ""),
                "courses": len(r.get("courses", [])),
            }
            for r in programme.get("reunions", [])
        ],
    }
    out = os.path.join(DATA_DIR, "programme.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(public_programme, f, ensure_ascii=False, indent=2)
    print(f"  [OK] programme.json")


def _github_request(method, path, body=None):
    """Effectue une requête vers l'API GitHub."""
    url = f"{GITHUB_API}{path}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "nano-pmu-bot",
        "Content-Type": "application/json",
    }
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def push_to_github(date_str):
    """
    Pousse les fichiers JSON publics vers GitHub via l'API.
    Déclenche automatiquement un rebuild Vercel.
    """
    if not GITHUB_TOKEN or not GITHUB_REPO:
        print("[WARN] GITHUB_TOKEN ou GITHUB_REPO non configuré — push ignoré")
        return False

    print(f"[GITHUB] Push vers {GITHUB_REPO}...")
    files_to_push = ["pronostics.json", "risklist.json", "programme.json"]
    pushed = 0

    for filename in files_to_push:
        filepath = os.path.join(DATA_DIR, filename)
        if not os.path.exists(filepath):
            print(f"  [SKIP] {filename} (fichier introuvable)")
            continue

        with open(filepath, "rb") as f:
            content_b64 = base64.b64encode(f.read()).decode()

        api_path = f"/repos/{GITHUB_REPO}/contents/data/{filename}"

        # Récupérer le SHA actuel (nécessaire pour update)
        existing = _github_request("GET", api_path)
        sha = existing.get("sha", "") if existing else ""

        body = {
            "message": f"🏇 Auto-update {filename}: {date_str}",
            "content": content_b64,
        }
        if sha:
            body["sha"] = sha

        _github_request("PUT", api_path, body)
        print(f"  [OK] {filename} → GitHub")
        pushed += 1

    print(f"[GITHUB] {pushed}/{len(files_to_push)} fichiers poussés → Vercel rebuild déclenché")
    return pushed > 0


# ============================================================================
# FONCTION PRINCIPALE
# ============================================================================

def publish():
    """Exécute la publication complète."""
    print("=" * 60)
    print("DEMARRAGE PUBLICATION - Daily Racing Hub")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    today = datetime.now().strftime("%Y-%m-%d")

    # 1. Charger les données
    pronostics, risklist, programme = load_latest_data()

    # 2. Générer les fichiers publics
    generate_public_data(pronostics, risklist, programme)

    # 3. Pousser vers GitHub (→ Vercel rebuild)
    push_to_github(today)

    print()
    print("=" * 60)
    print("PUBLICATION TERMINEE")
    print("=" * 60)
    print(f"Courses publiées: {len(pronostics.get('courses', []))}")
    print(f"Recommandées: {risklist.get('total_recommended', 0)}")
    print("=" * 60)

    return True


def run():
    """Point d'entrée appelé par le scheduler."""
    return publish()


if __name__ == "__main__":
    publish()
