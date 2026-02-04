# Onyx Bot

**Bot Discord communautaire** — Engagement, analytics et rêves lucides.

Onyx est un bot Discord modulaire construit avec discord.py. Il suit l'activité d'un serveur en temps réel, attribue de l'XP aux membres, génère des classements hebdomadaires et collecte des analytics détaillées sur les conversations. Le tout avec un système de cogs extensible et une persistance JSON automatique.

---

## Aperçu des fonctionnalités

| Module | Ce qu'il fait |
|---|---|
| **Engagement** | XP par message, niveaux progressifs, streaks, profil, classement hebdo |
| **Analytics** | Collecte 24/7 : mots, emojis, conversations, mentions, réactions, archive complète |
| **Good Morning** | Réponse personnalisée au "gm" quotidien, bonus XP |
| **Rêves Lucides** | Conseils aléatoires et ressources éducatives |
| **Reactions** | Le bot réagit automatiquement aux emojis `:hap:` et `:noel:` |
| **Error Handler** | Suggestion de la bonne commande en cas de faute de frappe |

---

## Démarrage rapide

### Prérequis

- Python 3.10+
- Un bot Discord avec l'intent `message_content` activé

### Installation

```bash
git clone https://github.com/Alexandre78500/Onyx_Bot_Final.git
cd Onyx_Bot_Final

python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux / Mac

pip install -r requirements.txt
```

### Configuration

Copier `.env.example` vers `.env` et renseigner les valeurs :

```env
DISCORD_TOKEN=ton_token_ici
GUILD_ID=123456789            # Optionnel — sync rapide en dev
```

### Lancement

```bash
mkdir data
python -m bot.main
```

---

## Commandes

### Commandes préfixées (`o!`)

| Commande | Aliases | Description | Canal |
|---|---|---|---|
| `o!profil` | `rang`, `rank`, `stats`, `niveau` | Carte profil : niveau, XP, position, emoji favori, mot favori, tranche horaire | Général uniquement |
| `o!classement` | `top`, `ranking`, `leaderboard`, `top10` | Top 10 du serveur + position perso + écart XP + progression | Général uniquement |
| `o!conseil` | `tip`, `astuce` | Conseil aléatoire pour faire des rêves lucides | Canaux lucid |
| `o!ressource` | `lien`, `resources` | Lien vers des ressources éducatives | Canaux lucid |
| `o!help` | `aide` | Affiche la liste des commandes | Partout |

### Fonctionnalités automatiques

| Déclencheur | Comportement |
|---|---|
| Envoyer un message | +8 XP (cooldown 15s) |
| Écrire `gm` | Réponse personnalisée + 50 XP bonus (1x/jour, reset à 5h30) |
| Monter de niveau | Félicitations automatiques dans le canal |
| `:hap:` ou `:noel:` dans un message | Le bot réagit avec l'emoji correspondant |
| Faute de frappe sur une commande | Suggestion de la commande la plus proche |
| Dimanche 20h | Publication automatique du classement hebdomadaire |

---

## Architecture

### Arborescence

```
bot/
  __init__.py
  main.py                  # Point d'entrée, chargement des cogs
  config.py                # Lecture du .env (token, guild_id)
  constants.py             # Toutes les constantes : XP, cooldowns, timers, canaux
  command_limits.py        # Restrictions de canaux et notifications
  cogs/
    __init__.py
    analytics.py           # Collecte de données (602 lignes)
    engagement.py          # Système XP et niveaux (841 lignes)
    gm.py                  # Good morning quotidien (219 lignes)
    lucid.py               # Commandes rêves lucides
    reactions.py           # Réactions automatiques aux emojis
    error_handler.py       # Suggestions de commandes
    help.py                # Commande help personnalisée

data/                      # Créé automatiquement
  analytics_v1.json        # Stats globales (JSON)
  messages_archive_v1.jsonl  # Archive complète (JSON Lines)
  analytics_config.json    # Config analytics

engagement_data.json       # Données XP par serveur (racine)
gm_data.json               # Suivi GM par serveur (racine)
```

### Pattern général

Chaque fonctionnalité est un **cog** indépendant (`bot/cogs/*.py`). Les cogs sont chargés automatiquement au démarrage dans `main.py:setup_hook()`. Ils utilisent :

- `@commands.command()` pour les commandes préfixées
- `@commands.Cog.listener()` pour les événements (messages, réactions)
- `@tasks.loop()` pour les tâches périodiques (sauvegarde, reset hebdo)

Le préfixe est `o!` (insensible à la casse).

### Persistance des données

| Composant | Fichier | Format | Sauvegarde | Perte max en cas de crash |
|---|---|---|---|---|
| Analytics | `data/analytics_v1.json` | JSON | Toutes les 5 min | ~5 min |
| Archive messages | `data/messages_archive_v1.jsonl` | JSONL | Buffer de 100 messages | ~100 messages |
| Engagement | `engagement_data.json` | JSON | Toutes les 60s | ~60s |
| Good Morning | `gm_data.json` | JSON | Toutes les 60s | ~60s |

Toutes les écritures passent par un executor async pour ne pas bloquer l'event loop. Les données sont aussi sauvegardées proprement à l'arrêt du bot (`cog_unload`).

---

## Système d'engagement

### Gain d'XP

- **8 XP par message** avec un cooldown de 15 secondes (anti-spam)
- **+50 XP** bonus pour le GM quotidien
- L'XP hebdomadaire est resetée chaque dimanche à 20h (Europe/Paris)

### Calcul du niveau

Formule exponentielle : il faut `100 * niveau^1.5` XP pour passer au niveau suivant.

```python
def calculate_level(xp):
    level = 1
    while xp >= 100 * (level ** 1.5):
        xp -= int(100 * (level ** 1.5))
        level += 1
    return level
```

Les premiers niveaux sont rapides, puis ça ralentit progressivement.

### Streaks

Le bot compte les jours consécutifs d'activité. La date de dernière activité est stockée par utilisateur — si l'écart dépasse un jour, le streak retombe à zéro.

### Classement hebdomadaire

Chaque dimanche à 20h, le bot publie automatiquement le top du serveur dans le canal configuré. L'XP hebdomadaire est ensuite remise à zéro pour tout le monde.

---

## Analytics

Le cog analytics collecte des données sur chaque message envoyé, sans aucune commande nécessaire.

### Données collectées

| Métrique | Détail |
|---|---|
| **Messages** | Total, par jour de la semaine (lun-dim), par heure (0-23), par tranche (nuit/matin/aprèm/soir) |
| **Mots** | Fréquence des mots (min. 3 lettres, hors mots courants). Top 50, nettoyé 1x/jour |
| **Emojis** | Emojis texte utilisés par chaque utilisateur |
| **Conversations** | Graphe de qui répond à qui (replies Discord + heuristique < 5 min) |
| **Mentions** | Graphe de qui mentionne qui (donné/reçu) |
| **Réactions** | Total et comptage par emoji |
| **Archive** | Chaque message sauvegardé en JSONL : timestamp, auteur, contenu, mentions, reply, pièces jointes |

### Schéma (v1)

Le fichier `data/analytics_v1.json` contient un objet `_meta` (version, dates) et un objet par guild avec toutes les stats dans `global_stats`. Le système supporte les migrations de schéma : incrémenter `CURRENT_SCHEMA_VERSION` dans `analytics.py` et ajouter la logique dans `_migrate_if_needed()`.

L'archive `messages_archive_v1.jsonl` utilise le format JSON Lines (une ligne JSON par message) pour permettre l'append sans recharger tout le fichier.

---

## Configuration

Toutes les constantes sont centralisées dans `bot/constants.py` :

| Constante | Valeur | Rôle |
|---|---|---|
| `ENGAGEMENT_COOLDOWN_SECONDS` | 15 | Anti-spam XP |
| `XP_PER_MESSAGE_MIN` / `MAX` | 8 / 8 | XP gagné par message |
| `XP_GM_BONUS` | 50 | Bonus XP pour le GM |
| `GM_RESET_TIME` | 05:30 | Heure de reset du GM quotidien |
| `ENGAGEMENT_SAVE_INTERVAL_SECONDS` | 60 | Fréquence sauvegarde engagement |
| `ANALYTICS_SAVE_INTERVAL_MINUTES` | 5 | Fréquence sauvegarde analytics |
| `ANALYTICS_ARCHIVE_BUFFER_SIZE` | 100 | Taille du buffer avant flush archive |
| `ANALYTICS_WORD_COUNT_TOP_N` | 50 | Nombre de mots conservés |

Les canaux autorisés pour les commandes sont aussi définis dans ce fichier (`COMMAND_CHANNEL_IDS_GENERAL_ONLY`, `COMMAND_CHANNEL_IDS_LUCID`).

---

## Étendre le bot

### Ajouter un cog

1. Créer `bot/cogs/mon_cog.py` en suivant le pattern des cogs existants (voir `lucid.py` pour un exemple simple, `engagement.py` pour un exemple complet)
2. Ajouter `await self.load_extension("bot.cogs.mon_cog")` dans `main.py:setup_hook()`
3. Mettre à jour `help.py` si le cog ajoute des commandes

### Ajouter des données analytics

1. Ajouter le champ dans `_create_empty_guild_stats()`
2. Ajouter la logique de collecte dans le listener `on_message` ou `on_raw_reaction_add`
3. Incrémenter `CURRENT_SCHEMA_VERSION` et gérer la migration dans `_migrate_if_needed()`

---

## Déploiement (systemd)

```bash
sudo cp discord-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable discord-bot
sudo systemctl start discord-bot

# Consulter les logs
sudo journalctl -u discord-bot -f
```

---

## Dépannage

| Problème | Solution |
|---|---|
| Les commandes ne répondent pas | Vérifier `DISCORD_TOKEN` dans `.env` et l'intent `message_content` |
| Données non sauvegardées | Vérifier les permissions du dossier `data/` et l'espace disque |
| Bot silencieux | Vérifier les permissions Discord (lire/envoyer des messages) |
| Reset complet des données | Arrêter le bot, supprimer les fichiers JSON dans `data/` et à la racine, relancer |

---

## Dépendances

| Package | Version | Rôle |
|---|---|---|
| discord.py | >= 2.4.0 | Framework Discord |
| python-dotenv | >= 1.0.0 | Lecture du `.env` |
| pytz | >= 2024.1 | Timezone Europe/Paris |

---

Projet privé — Tous droits réservés.

Créé pour la communauté Onyx. Dernière mise à jour : février 2026.
