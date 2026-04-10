# 🏇 nano-pmu

Bot Telegram de pronostics PMU automatiques pour Daily Racing Hub.

## Architecture

```
nano-pmu/
├── bot.py              # Orchestrateur principal + commandes manuelles
├── scheduler.py        # Cron automatique (12h/12h30/13h/20h)
├── skills/
│   ├── pmu_scraper.py   # Collecte API PMU (offline + online)
│   ├── pmu_analyser.py  # Scoring 5 critères → pronostics
│   ├── pmu_publisher.py # JSON publics + push GitHub → Vercel
│   ├── pmu_resultats.py # Résultats réels + calcul ROI + bankroll
│   └── pmu_telegram.py  # Notifications Telegram (pronostics + bilan)
├── data/               # Fichiers JSON générés quotidiennement
├── memory/
│   └── bankroll.json   # Bankroll persistante (initial: 100€)
├── .env.example        # Template secrets
└── requirements.txt
```

## Pipeline quotidien

| Heure | Action |
|-------|--------|
| 12h00 | Scraping API PMU (programme + cotes + performances) |
| 12h30 | Analyse multi-critères → pronostics.json + risklist.json |
| 13h00 | Push GitHub → Vercel rebuild + Telegram pronostics |
| 20h00 | Résultats PMU + calcul ROI + bankroll + Telegram bilan |

## Installation

```bash
pip install -r requirements.txt
cp .env.example .env
# Remplir .env avec vos tokens
```

## Commandes manuelles

```bash
python bot.py              # Lance le scheduler (mode production)
python bot.py scrape       # Scraping maintenant
python bot.py analyse      # Analyse maintenant
python bot.py publish      # Publication maintenant
python bot.py resultats    # Résultats maintenant
python bot.py pronostics   # Envoie Telegram pronostics
python bot.py bilan        # Envoie Telegram bilan
python bot.py all          # Pipeline complet (test)
```

## Variables d'environnement

| Variable | Description |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Token bot (@BotFather) |
| `TELEGRAM_CHAT_ID` | ID du canal (@userinfobot) |
| `GITHUB_TOKEN` | Token GitHub (scope: repo) |
| `GITHUB_REPO` | Format: `username/repo-name` |

## Déploiement Railway

```bash
# 1. Créer un projet Railway
railway login
railway init

# 2. Configurer les variables
railway variables set TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... GITHUB_TOKEN=... GITHUB_REPO=...

# 3. Déployer
railway up
```

> Railway démarre automatiquement `python bot.py` via le `Procfile`.

## Fichiers JSON générés

| Fichier | Contenu |
|---------|---------|
| `data/programme_{date}.json` | Programme PMU complet du jour |
| `data/cotes_{date}.json` | Partants + cotes par course |
| `data/performances_{date}.json` | 5 dernières courses par cheval |
| `data/pronostics_{date}.json` | Pronostics scorés (top 5 par course) |
| `data/risklist_{date}.json` | Courses LOW/MEDIUM/HIGH risk |
| `data/resultats_{date}.json` | Résultats officiels PMU |
| `data/bilan_{date}.json` | ROI + gains/pertes du jour |
| `data/pronostics.json` | ← Symlink public pour Vercel |
| `data/risklist.json` | ← Symlink public pour Vercel |
| `data/programme.json` | ← Symlink public pour Vercel |
| `memory/bankroll.json` | Bankroll cumulative depuis le début |
