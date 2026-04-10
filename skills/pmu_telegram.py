#!/usr/bin/env python3
"""
=============================================================================
SKILL 5: NOTIFICATIONS TELEGRAM (pmu_telegram.py)
=============================================================================
BUT: Envoyer les pronostics et bilans quotidiens sur Telegram
EXECUTION:
- 13h00 → send_pronostics() (après publication)
- 20h00 → send_bilan() (après résultats)
=============================================================================
"""

import json
import os
import asyncio
from datetime import datetime

# ============================================================================
# CONFIGURATION
# ============================================================================

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SKILL_DIR)
DATA_DIR = os.path.join(PROJECT_DIR, "data")
MEMORY_DIR = os.path.join(PROJECT_DIR, "memory")

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")


# ============================================================================
# HELPERS
# ============================================================================

def risk_emoji(risk):
    return {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🔴"}.get(risk, "⚪")


def stars(n):
    return "⭐" * max(1, min(5, int(n)))


def load_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def load_bankroll():
    path = os.path.join(MEMORY_DIR, "bankroll.json")
    data = load_json(path)
    if data:
        return data.get("current", 100)
    return 100


async def _send_async(message):
    """Envoie un message Telegram via python-telegram-bot (async)."""
    try:
        from telegram import Bot
        bot = Bot(token=TELEGRAM_TOKEN)
        # Limiter à 4096 caractères max (limite Telegram)
        if len(message) > 4096:
            message = message[:4090] + "\n..."
        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
            parse_mode="HTML",
        )
        return True
    except Exception as e:
        print(f"[TELEGRAM] Erreur envoi: {e}")
        return False


def send_message(message):
    """Wrapper synchrone pour envoyer un message Telegram."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("[TELEGRAM] TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID non configuré")
        print("[TELEGRAM] Message (non envoyé):")
        print(message)
        return False
    return asyncio.run(_send_async(message))


# ============================================================================
# FORMAT DES MESSAGES
# ============================================================================

def format_pronostics_message(pronostics, risklist, bankroll_current):
    """
    Formate le message de pronostics du jour.

    Format:
    🏇 PRONOSTICS DU JOUR — {date}

    📍 {course_id} — {hippodrome} {heure} — {discipline}
    {emoji_risk} {risk} RISK
    1. {cheval} (n°{numero}) — cote {cote} ⭐⭐⭐
    2. ...
    3. ...

    💰 Mise recommandée : {mise}€
    📊 Bankroll : {bankroll}€
    """
    today = pronostics.get("date", datetime.now().strftime("%Y-%m-%d"))
    courses = pronostics.get("courses", [])

    # Séparer par niveau de risque
    low = [c for c in courses if c["risk"] == "LOW"]
    medium = [c for c in courses if c["risk"] == "MEDIUM"]

    lines = [
        f"🏇 <b>PRONOSTICS DU JOUR — {today}</b>",
        f"📋 {len(courses)} courses analysées | "
        f"🟢 {len(low)} recommandées | 🟡 {len(medium)} avec prudence",
        "",
    ]

    mise_totale = 0

    # Afficher d'abord les LOW risk
    for course in low + medium:
        risk = course["risk"]
        pronos = course.get("pronostics", [])[:3]
        mise = course.get("mise_totale", 0)
        mise_totale += mise

        lines.append(
            f"📍 <b>{course['id']}</b> — {course['hippodrome']} "
            f"{course.get('heure', '?')} — {course.get('discipline', '')}"
        )
        lines.append(f"{risk_emoji(risk)} <b>{risk} RISK</b> | {course.get('distance', 0)}m | {course.get('partants_count', 0)} partants")

        for i, p in enumerate(pronos, 1):
            cote_str = f"cote {p['cote']}" if p.get("cote") else "N/C"
            lines.append(
                f"{i}. <b>{p['cheval']}</b> (n°{p['numero']}) — {cote_str} {stars(p.get('confidence', 1))}"
            )

        lines.append(f"💰 Mise : {mise}€")
        lines.append("")

    lines.append(f"━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"💰 <b>Mise totale du jour : {mise_totale}€</b>")
    lines.append(f"📊 <b>Bankroll actuel : {bankroll_current:.2f}€</b>")
    lines.append(f"🔗 DailyRacingHub — Bonne chance ! 🍀")

    return "\n".join(lines)


def format_bilan_message(bilan, bankroll_current):
    """
    Formate le message de bilan du soir.
    """
    date = bilan.get("date", datetime.now().strftime("%Y-%m-%d"))
    gagnes = bilan.get("gagnes", 0)
    perdues = bilan.get("perdues", 0)
    mise = bilan.get("mise_totale", 0)
    gain = bilan.get("gain_total", 0)
    profit = bilan.get("profit", 0)
    roi = bilan.get("roi", 0)

    profit_emoji = "📈" if profit >= 0 else "📉"
    profit_str = f"+{profit:.2f}€" if profit >= 0 else f"{profit:.2f}€"
    roi_str = f"+{roi:.1f}%" if roi >= 0 else f"{roi:.1f}%"

    lines = [
        f"🏁 <b>BILAN DU JOUR — {date}</b>",
        "",
        f"✅ Gagnées : <b>{gagnes}</b> | ❌ Perdues : <b>{perdues}</b>",
        f"💶 Misé : <b>{mise:.2f}€</b> | Récupéré : <b>{gain:.2f}€</b>",
        f"{profit_emoji} Profit : <b>{profit_str}</b> | ROI : <b>{roi_str}</b>",
        "",
    ]

    # Détails des courses
    details = bilan.get("details", [])
    if details:
        lines.append("📋 <b>Détails :</b>")
        for d in details:
            icon = "✅" if d.get("resultat") == "GAGNE" else "❌"
            arrivee = d.get("arrivee", [])[:3]
            arrivee_str = " - ".join(str(n) for n in arrivee) if arrivee else "?"
            lines.append(
                f"{icon} {d['course']} {d.get('hippodrome', '')} | "
                f"Prono: n°{d.get('pronostic_numero', '?')} {d.get('pronostic', '?')} | "
                f"Arrivée: {arrivee_str}"
            )
        lines.append("")

    lines.append(f"━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"📊 <b>Bankroll : {bankroll_current:.2f}€</b>")

    return "\n".join(lines)


# ============================================================================
# FONCTIONS PUBLIQUES
# ============================================================================

def send_pronostics():
    """Envoie les pronostics du jour sur Telegram (appelé à 13h00)."""
    print("[TELEGRAM] Envoi des pronostics...")
    today = datetime.now().strftime("%Y-%m-%d")

    pronostics = load_json(os.path.join(DATA_DIR, "pronostics.json"))
    risklist = load_json(os.path.join(DATA_DIR, "risklist.json"))
    bankroll = load_bankroll()

    if not pronostics or not pronostics.get("courses"):
        print("[TELEGRAM] Aucun pronostic disponible")
        send_message("⚠️ <b>Aucun pronostic disponible aujourd'hui.</b>")
        return False

    message = format_pronostics_message(pronostics, risklist, bankroll)
    success = send_message(message)

    if success:
        print("[TELEGRAM] Pronostics envoyés avec succès")
    return success


def send_bilan():
    """Envoie le bilan du jour sur Telegram (appelé à 20h00)."""
    print("[TELEGRAM] Envoi du bilan...")
    today = datetime.now().strftime("%Y-%m-%d")

    bilan = load_json(os.path.join(DATA_DIR, f"bilan_{today}.json"))
    bankroll = load_bankroll()

    if not bilan:
        print("[TELEGRAM] Aucun bilan disponible")
        send_message("⚠️ <b>Bilan non disponible pour aujourd'hui.</b>")
        return False

    message = format_bilan_message(bilan, bankroll)
    success = send_message(message)

    if success:
        print("[TELEGRAM] Bilan envoyé avec succès")
    return success


def send_alert(text):
    """Envoie une alerte manuelle sur Telegram."""
    return send_message(f"⚠️ <b>ALERTE</b>\n\n{text}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "bilan":
        send_bilan()
    else:
        send_pronostics()
