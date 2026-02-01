# 🤖 Onyx Bot - Discord Bot Rêves Lucides & Analytics

Bot Discord complet avec système de rêves lucides, engagement utilisateur et analytics avancées.

## 📋 Table des matières
- [Fonctionnalités](#-fonctionnalités)
- [Architecture](#-architecture)
- [Fichiers de données](#-fichiers-de-données)
- [Installation](#-installation)
- [Commandes](#-commandes)
- [Configuration](#-configuration)
- [Développement](#-développement)
- [Schéma de données](#-schéma-de-données)

---

## ✨ Fonctionnalités

### 🌙 Système Rêves Lucides
- `o!conseil` - Conseils aléatoires pour faire des rêves lucides
- `o!ressource` - Liens vers des ressources éducatives

### 📊 Système d'Engagement (XP & Niveaux)
- **Gain d'XP automatique** : 5-15 XP par message (cooldown 15s)
- **Niveaux progressifs** : Algorithmes de niveau avec courbe d'XP croissante
- **Félicitations automatiques** : Messages de félicitations quand on monte de niveau
- **Classement** : `o!rang` (profil perso) et `o!classement` (top 10 serveur)
- **Streak journalier** : Nombre de jours consécutifs d'activité
- **Classement hebdomadaire** : Post automatique le dimanche à 20h

### 🤖 Features Automatiques
- **GM** : Réponds "gm" pour recevoir un message personnalisé (1x/jour par serveur)
- **Réactions auto** : Le bot réagit avec `:hap:` et `:noel:` quand ces emojis sont utilisés
- **Suggestions de commandes** : Si tu fais une faute (ex: `o!classsement`), le bot suggère la bonne commande (liste auto)

### 📈 Analytics Complètes
Collecte automatique à chaque message :
- **Stats temporelles** : Messages par jour de la semaine (7 valeurs) et par heure (24 valeurs)
- **Tranches horaires** : Activite par segments (nuit, matin, apres-midi, soir)
- **Word count** : Top mots utilisés sur le serveur (exclut les mots communs)
- **Top 50 mots** : Nettoyage automatique 1x/jour pour garder les 50 mots les plus frequents
- **Emojis texte favoris** : Top emojis par utilisateur (uniquement dans le texte)
- **Graphe de conversations** : Qui répond à qui (réponses explicites si dispo, sinon messages < 5 min)
- **Graphe de mentions** : Qui mentionne qui fréquemment
- **Stats réactions** : Nombre total de réactions et par emoji
- **Archive complète** : Tous les messages sauvegardés avec timestamp, auteur, contenu, mentions, etc.

---

## 🏗️ Architecture

### Structure du projet
```
bot/
├── __init__.py
├── main.py                 # Point d'entrée, chargement des cogs
├── config.py              # Configuration environnement
├── constants.py            # Constantes centralisées (timers, XP, seuils)
└── cogs/
    ├── __init__.py
    ├── analytics.py       # 📈 Cog analytics (collecte données)
    ├── engagement.py      # 📊 Cog XP/niveaux/classements
    ├── error_handler.py   # 💡 Suggestions commandes
    ├── gm.py             # 🌅 Système GM (good morning)
    ├── help.py           # ❓ Commande help
    ├── lucid.py          # 🌙 Commandes rêves lucides
    └── reactions.py      # 😄 Réactions auto aux emojis

data/                     # Dossier données (créé auto)
├── analytics_v1.json     # Stats globales (JSON)
├── messages_archive_v1.jsonl  # Archive messages (JSONL)
└── analytics_config.json # Configuration analytics

# Autres fichiers
engagement_data.json      # Données XP par serveur
gm_data.json             # Données GM par serveur
```

### Pattern Cogs (discord.py)
- Chaque fonctionnalité = un cog séparé
- Cogs chargés automatiquement dans `main.py:setup_hook()`
- Gestion des événements via `@commands.Cog.listener()`
- Commandes préfixées uniquement (`o!`) pour l'instant

### Constantes centralisées
- Les timers (save/reset), XP, cooldowns et tailles de cache sont regroupés dans `bot/constants.py`
- Modifier ces valeurs ici évite de chercher dans plusieurs fichiers

### Gestion des données
- **Format** : JSON pour les stats, JSONL pour l'archive
- **Persistance** :
  - Analytics : sauvegarde toutes les 5 minutes + au shutdown
  - Engagement / GM : sauvegarde toutes les 60s si données modifiées + au shutdown
- **En mémoire** : Données chargées en RAM pour accès instantané
- **I/O async** : Écritures via executor + buffer (évite de bloquer l'event loop)
- **Tolérance** : Perte max ~60s en cas de crash brutal (données en buffer)

---

## 📁 Fichiers de données

### 1. `data/analytics_v1.json`
**Contenu** : Statistiques globales du serveur

```json
{
  "_meta": {
    "schema_version": 1,
    "created_at": "2026-02-01T20:00:00",
    "last_migration": "2026-02-01T20:00:00",
    "guilds": ["123456789"],
    "last_word_prune": "2026-02-01"
  },
  "123456789": {
    "global_stats": {
      "messages_total": 1250,
      "messages_by_day": [45, 32, 67, 89, 120, 200, 150],
      "messages_by_hour": [0,0,0,0,2,5,12,45,89,120...],
      "messages_by_segment": {"night": 12, "morning": 120, "afternoon": 340, "evening": 778},
      "unique_users": ["user_id_1", "user_id_2"],
      "unique_channels": ["channel_id_1"],
      "word_counts": {"rêve": 150, "technique": 89, "fille": 45},
      "emoji_text_usage": {
        "users": {"user_id_1": {"😀": 12, ":hap:": 4}}
      },
      "conversations": {"user1_user2": 15, "user1_user3": 8},
      "mentions_graph": {
        "given": {"user1": {"user2": 5}},
        "received": {"user2": {"user1": 5}}
      },
      "reactions_stats": {
        "total_added": 450,
        "by_emoji": {"hap": 120, "noel": 89}
      }
    }
  },
  "_schema_history": []
}
```

**Champs importants :**
- `messages_by_day[0-6]` : Lundi (0) à Dimanche (6)
- `messages_by_hour[0-23]` : 00h à 23h
- `messages_by_segment` : Activite par tranches (night, morning, afternoon, evening)
- `conversations["userA_userB"]` : Nombre de réponses entre ces deux users
- `word_counts` : Tous les mots (≥3 lettres, hors mots communs) avec leur fréquence
- `emoji_text_usage.users` : Emojis utilises dans le texte par utilisateur
- `_meta.guilds` : Optionnel (liste ou dict historique, non critique pour la migration)
- `_meta.last_word_prune` : Derniere date de nettoyage du top 50

### 2. `data/messages_archive_v1.jsonl`
**Format** : JSON Lines (1 ligne = 1 message JSON)

```json
{"ts":"2026-02-01T20:15:30","guild":"123","channel":"456","author":"789","author_name":"Pseudo","content":"Bonjour !","mentions":["321"],"has_attachments":false,"is_reply_to":null,"msg_id":"abc123"}
{"ts":"2026-02-01T20:16:45","guild":"123","channel":"456","author":"321","author_name":"Autre","content":"Salut !","mentions":["789"],"has_attachments":false,"is_reply_to":"abc123"}
```

**Champs :**
- `ts` : ISO 8601 timestamp
- `guild` : ID du serveur
- `channel` : ID du canal
- `author` : ID de l'auteur
- `author_name` : Nom affiché au moment du message
- `content` : Contenu textuel
- `mentions` : Liste des IDs mentionnés
- `has_attachments` : Booléen (images, fichiers)
- `is_reply_to` : ID du message parent (si réponse)
- `msg_id` : ID unique du message

### 3. `engagement_data.json`
**Contenu** : Données XP et niveaux par serveur

```json
{
  "guilds": {
    "123456789": {
      "users": {
        "user_id": {
          "xp": 1250,
          "weekly_xp": 150,
          "messages": 89,
          "last_active": "2026-02-01T20:15:30",
          "display_name": "Pseudo",
          "streak_days": 5,
          "last_streak_date": "2026-02-01T20:15:30"
        }
      },
      "weekly_reset": "2026-02-07T20:00:00",
      "channel_id": 456789
    }
  }
}
```

### 4. `gm_data.json`
**Contenu** : Suivi des GM quotidiens

```json
{
  "guild_id": {
    "user_id": ["2026-02-01", true],
    "user_id2": ["2026-02-01", false]
  }
}
```

---

## 🚀 Installation

### Prérequis
- Python 3.10+
- pip
- Virtualenv (recommandé)

### Setup

```bash
# 1. Cloner le repo
git clone https://github.com/Alexandre78500/Onyx_Bot_Final.git
cd Onyx_Bot_Final

# 2. Créer l'environnement virtuel
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# ou
.venv\Scripts\activate  # Windows

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Configuration
cp .env.example .env
# Éditer .env avec votre token

# 5. Créer le dossier data
mkdir data

# 6. Lancer
python -m bot.main
```

### Déploiement VPS (systemd)

```bash
# Copier le service
sudo cp discord-bot.service /etc/systemd/system/
sudo systemctl daemon-reload

# Activer et démarrer
sudo systemctl enable discord-bot
sudo systemctl start discord-bot

# Logs
sudo journalctl -u discord-bot.service -f
```

---

## 💬 Commandes

### Commandes de base
- `o!help` / `o!aide` - Afficher l'aide
- `o!conseil` / `o!tip` - Conseil rêve lucide aléatoire
- `o!ressource` / `o!lien` - Ressources sur les rêves lucides

### Commandes Engagement
- `o!rang` / `o!stats` - Voir ton profil (niveau, XP, position, streak)
- `o!classement` / `o!top` - Top 10 du serveur

### Aliases disponibles
Chaque commande a plusieurs aliases pour être facilement trouvée :
- `rang` : rank, stats, profil, niveau
- `classement` : ranking, top, leaderboard, top10
- `conseil` : tip, astuce
- `ressource` : lien, resources

### Features automatiques
- **Dis `gm`** → Le bot répond avec un message personnalisé (1x/jour)
- **Parle normalement** → Gagne de l'XP (5-15 par message, cooldown 15s)
- **Niveau up** → Félicitations automatiques
- **`:hap:` ou `:noel:`** dans un message → Le bot réagit avec l'emoji
- **Faute de frappe** → Suggestion de la bonne commande (ex: `o!classsement`)

---

## ⚙️ Configuration

### Variables d'environnement (.env)

```bash
DISCORD_TOKEN=your_bot_token_here
GUILD_ID=123456789  # Optionnel - pour sync rapide dev
```

### Configuration dans les cogs

**`engagement.py`** :
- `COOLDOWN_SECONDS = 15` - Anti-spam XP
- `XP_PER_MESSAGE_MIN/MAX = 5/15` - XP par message
- Reset hebdomadaire : Dimanche 20h (Europe/Paris)

**`gm.py`** :
- `RESET_TIME = time(5, 30)` - Reset quotidien à 5h30
- `GM_RESPONSES` - Liste des réponses personnalisées

**`analytics.py`** :
- `SAVE_INTERVAL_MINUTES = 5` - Sauvegarde auto
- `ARCHIVE_BUFFER_SIZE = 100` - Messages avant flush
- `COMMON_WORDS` - Mots exclus du word count

---

## 🛠️ Développement

### Ajouter un nouveau cog

1. Créer `bot/cogs/nom_du_cog.py` :
```python
from discord.ext import commands

class NomDuCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @commands.command(name="commande")
    async def ma_commande(self, ctx):
        await ctx.send("Hello!")

async def setup(bot: commands.Bot):
    await bot.add_cog(NomDuCog(bot))
```

2. Charger dans `main.py` :
```python
await self.load_extension("bot.cogs.nom_du_cog")
```

### Ajouter une nouvelle donnée analytics

1. Modifier `_create_empty_guild_stats()` dans `analytics.py`
2. Ajouter la logique de collecte dans `on_message()` ou autre listener
3. Incrémenter `CURRENT_SCHEMA_VERSION`
4. Ajouter la migration dans `_migrate_if_needed()`

### Structure d'un cog typique

```python
class ExempleCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data = {}
        self._load_data()
        self.task.start()
    
    def _load_data(self):
        # Charger depuis JSON
        pass
    
    def _save_data(self):
        # Sauvegarder vers JSON
        pass
    
    @commands.Cog.listener()
    async def on_message(self, message):
        # Réagir aux messages
        pass
    
    @commands.command(name="exemple")
    async def exemple_cmd(self, ctx):
        # Commande préfixée
        pass
    
    @tasks.loop(minutes=5)
    async def task(self):
        # Tâche périodique
        pass
    
    def cog_unload(self):
        self.task.cancel()
        self._save_data()
```

---

## 📊 Schéma de données

### Versions du schéma analytics

**v1 (actuel)** - Structure initiale :
- `global_stats` avec toutes les métriques
- Support multi-serveurs
- Archive JSONL

**Pour ajouter v2** :
1. Incrémenter `CURRENT_SCHEMA_VERSION = 2`
2. Ajouter dans `_migrate_if_needed()` :
```python
if current_version < 2:
    for guild_id in self.data:
        if guild_id.startswith("_"): continue
        self.data[guild_id]["global_stats"]["nouveau_champ"] = default_value
```
3. Ajouter dans `_schema_history`

### Algorithmes importants

**Calcul du niveau** (`engagement.py`) :
```python
def calculate_level(xp):
    level = 1
    while xp >= 100 * (level ** 1.5):
        xp -= 100 * (level ** 1.5)
        level += 1
    return level
```

**Détection conversation** (`analytics.py`) :
- Priorité aux réponses explicites (reply Discord)
- Sinon, utilise le cache des derniers messages du canal
- Si réponse < 5 minutes à quelqu'un d'autre = conversation
- Clé : `"userA_userB"` (trié alphabétiquement)

**Word count** :
- Minuscules
- Sans ponctuation
- Exclut `COMMON_WORDS` (liste de mots courants)
- Minimum 3 lettres

---

## 🔧 Dépannage

### Problèmes courants

**Les commandes ne fonctionnent pas :**
- Vérifier `DISCORD_TOKEN` dans `.env`
- Vérifier les intents (message_content=True)
- Voir logs : `sudo journalctl -u discord-bot -n 50`

**Les données ne se sauvegardent pas :**
- Vérifier permissions dossier `data/`
- Vérifier espace disque
- Voir erreurs dans les logs

**Le bot ne répond pas aux messages :**
- Vérifier intents `message_content=True` dans `main.py`
- Vérifier permissions du bot sur Discord (lire messages)

**Reset des données :**
```bash
# Arrêter le bot
sudo systemctl stop discord-bot

# Supprimer les données
rm data/analytics_v1.json
rm data/messages_archive_v1.jsonl
rm engagement_data.json
rm gm_data.json

# Relancer
sudo systemctl start discord-bot
```

---

## 📝 Notes pour IA / Maintenance

### Points d'extension courants

1. **Nouvelles commandes** : Ajouter dans le cog approprié, mettre à jour `help.py`
2. **Nouvelles données** : Modifier `analytics.py`, gérer migration
3. **Nouveaux triggers** : Ajouter `@commands.Cog.listener()` dans cog approprié
4. **Commandes slash** : Décommenter le code dans les cogs, sync dans `main.py`

### Fichiers critiques
- `bot/main.py` - Point d'entrée, chargement cogs
- `bot/cogs/analytics.py` - Toute la collecte de données
- `bot/cogs/engagement.py` - Système XP (dépend de analytics)
- `data/analytics_v1.json` - Stats globales (ne pas supprimer sans backup)

### Bonnes pratiques
- Toujours sauvegarder JSON après modification
- Utiliser `try/except` sur les appels Discord API
- Logger les erreurs avec `print()` ou `logging`
- Tester les migrations avec un fichier de test
- Documenter les changements de schéma

---

## 📄 Licence

Projet privé - Tous droits réservés.

---

## 👤 Auteur

Créé avec ❤️ pour la communauté Onyx.

**Dernière mise à jour** : Février 2026
