# Onyx Bot

**Bot Discord communautaire** — Engagement, analytics et reves lucides.

Onyx est un bot Discord modulaire construit avec discord.py. Il suit l'activite d'un serveur en temps reel, attribue de l'XP aux membres, genere des classements hebdomadaires et collecte des analytics detaillees sur les conversations. Le tout avec un systeme de cogs extensible et une persistance JSON automatique.

---

## Apercu des fonctionnalites

| Module | Ce qu'il fait |
|---|---|
| **Engagement** | XP par message, niveaux progressifs, streaks, profil, classement hebdo |
| **Analytics** | Collecte 24/7 : mots, emojis, conversations, mentions, reactions, archive complete |
| **Good Morning** | Reponse personnalisee au "gm" quotidien, bonus XP |
| **Reves Lucides** | Conseils aleatoires et ressources educatives |
| **Reactions** | Le bot reagit automatiquement aux emojis `:hap:` et `:noel:` |
| **Error Handler** | Suggestion de la bonne commande en cas de faute de frappe |

---

## Demarrage rapide

### Prerequis

- Python 3.10+
- Un bot Discord avec l'intent `message_content` active

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

### Commandes prefixees (`o!`)

| Commande | Aliases | Description | Canal |
|---|---|---|---|
| `o!profil` | `rang`, `rank`, `stats`, `niveau` | Carte profil : niveau, XP, position, emoji favori, mot favori, tranche horaire | General uniquement |
| `o!classement` | `top`, `ranking`, `leaderboard`, `top10` | Top 10 du serveur + position perso + ecart XP + progression | General uniquement |
| `o!conseil` | `tip`, `astuce` | Conseil aleatoire pour faire des reves lucides | Canaux lucid |
| `o!ressource` | `lien`, `resources` | Lien vers des ressources educatives | Canaux lucid |
| `o!help` | `aide` | Affiche la liste des commandes | Partout |

### Fonctionnalites automatiques

| Declencheur | Comportement |
|---|---|
| Envoyer un message | +8 XP (cooldown 15s) |
| Ecrire `gm` | Reponse personnalisee + 50 XP bonus (1x/jour, reset a 5h30) |
| Monter de niveau | Felicitations automatiques dans le canal |
| `:hap:` ou `:noel:` dans un message | Le bot reagit avec l'emoji correspondant |
| Faute de frappe sur une commande | Suggestion de la commande la plus proche |
| Dimanche 20h | Publication automatique du classement hebdomadaire |

---

## Architecture

### Arborescence

```
bot/
  __init__.py
  main.py                  # Point d'entree, chargement des cogs
  config.py                # Lecture du .env (token, guild_id)
  constants.py             # Toutes les constantes : XP, cooldowns, timers, canaux
  command_limits.py        # Restrictions de canaux et notifications
  cogs/
    __init__.py
    analytics.py           # Collecte de donnees (602 lignes)
    engagement.py          # Systeme XP et niveaux (841 lignes)
    gm.py                  # Good morning quotidien (219 lignes)
    lucid.py               # Commandes reves lucides
    reactions.py           # Reactions automatiques aux emojis
    error_handler.py       # Suggestions de commandes
    help.py                # Commande help personnalisee

data/                      # Cree automatiquement
  analytics_v1.json        # Stats globales (JSON)
  messages_archive_v1.jsonl  # Archive complete (JSON Lines)
  analytics_config.json    # Config analytics

engagement_data.json       # Donnees XP par serveur (racine)
gm_data.json               # Suivi GM par serveur (racine)
```

### Pattern general

Chaque fonctionnalite est un **cog** independant (`bot/cogs/*.py`). Les cogs sont charges automatiquement au demarrage dans `main.py:setup_hook()`. Ils utilisent :

- `@commands.command()` pour les commandes prefixees
- `@commands.Cog.listener()` pour les evenements (messages, reactions)
- `@tasks.loop()` pour les taches periodiques (sauvegarde, reset hebdo)

Le prefixe est `o!` (insensible a la casse).

### Persistance des donnees

| Composant | Fichier | Format | Sauvegarde | Perte max en cas de crash |
|---|---|---|---|---|
| Analytics | `data/analytics_v1.json` | JSON | Toutes les 5 min | ~5 min |
| Archive messages | `data/messages_archive_v1.jsonl` | JSONL | Buffer de 100 messages | ~100 messages |
| Engagement | `engagement_data.json` | JSON | Toutes les 60s | ~60s |
| Good Morning | `gm_data.json` | JSON | Toutes les 60s | ~60s |

Toutes les ecritures passent par un executor async pour ne pas bloquer l'event loop. Les donnees sont aussi sauvegardees proprement a l'arret du bot (`cog_unload`).

---

## Systeme d'engagement

### Gain d'XP

- **8 XP par message** avec un cooldown de 15 secondes (anti-spam)
- **+50 XP** bonus pour le GM quotidien
- L'XP hebdomadaire est resetee chaque dimanche a 20h (Europe/Paris)

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

Les premiers niveaux sont rapides, puis ca ralentit progressivement.

### Streaks

Le bot compte les jours consecutifs d'activite. La date de derniere activite est stockee par utilisateur — si l'ecart depasse un jour, le streak retombe a zero.

### Classement hebdomadaire

Chaque dimanche a 20h, le bot publie automatiquement le top du serveur dans le canal configure. L'XP hebdomadaire est ensuite remise a zero pour tout le monde.

---

## Analytics

Le cog analytics collecte des donnees sur chaque message envoye, sans aucune commande necessaire.

### Donnees collectees

| Metrique | Detail |
|---|---|
| **Messages** | Total, par jour de la semaine (lun-dim), par heure (0-23), par tranche (nuit/matin/aprem/soir) |
| **Mots** | Frequence des mots (min. 3 lettres, hors mots courants). Top 50, nettoye 1x/jour |
| **Emojis** | Emojis texte utilises par chaque utilisateur |
| **Conversations** | Graphe de qui repond a qui (replies Discord + heuristique < 5 min) |
| **Mentions** | Graphe de qui mentionne qui (donne/recu) |
| **Reactions** | Total et comptage par emoji |
| **Archive** | Chaque message sauvegarde en JSONL : timestamp, auteur, contenu, mentions, reply, pieces jointes |

### Schema (v1)

Le fichier `data/analytics_v1.json` contient un objet `_meta` (version, dates) et un objet par guild avec toutes les stats dans `global_stats`. Le systeme supporte les migrations de schema : incrementer `CURRENT_SCHEMA_VERSION` dans `analytics.py` et ajouter la logique dans `_migrate_if_needed()`.

L'archive `messages_archive_v1.jsonl` utilise le format JSON Lines (une ligne JSON par message) pour permettre l'append sans recharger tout le fichier.

---

## Configuration

Toutes les constantes sont centralisees dans `bot/constants.py` :

| Constante | Valeur | Role |
|---|---|---|
| `ENGAGEMENT_COOLDOWN_SECONDS` | 15 | Anti-spam XP |
| `XP_PER_MESSAGE_MIN` / `MAX` | 8 / 8 | XP gagne par message |
| `XP_GM_BONUS` | 50 | Bonus XP pour le GM |
| `GM_RESET_TIME` | 05:30 | Heure de reset du GM quotidien |
| `ENGAGEMENT_SAVE_INTERVAL_SECONDS` | 60 | Frequence sauvegarde engagement |
| `ANALYTICS_SAVE_INTERVAL_MINUTES` | 5 | Frequence sauvegarde analytics |
| `ANALYTICS_ARCHIVE_BUFFER_SIZE` | 100 | Taille du buffer avant flush archive |
| `ANALYTICS_WORD_COUNT_TOP_N` | 50 | Nombre de mots conserves |

Les canaux autorises pour les commandes sont aussi definis dans ce fichier (`COMMAND_CHANNEL_IDS_GENERAL_ONLY`, `COMMAND_CHANNEL_IDS_LUCID`).

---

## Etendre le bot

### Ajouter un cog

1. Creer `bot/cogs/mon_cog.py` en suivant le pattern des cogs existants (voir `lucid.py` pour un exemple simple, `engagement.py` pour un exemple complet)
2. Ajouter `await self.load_extension("bot.cogs.mon_cog")` dans `main.py:setup_hook()`
3. Mettre a jour `help.py` si le cog ajoute des commandes

### Ajouter des donnees analytics

1. Ajouter le champ dans `_create_empty_guild_stats()`
2. Ajouter la logique de collecte dans le listener `on_message` ou `on_raw_reaction_add`
3. Incrementer `CURRENT_SCHEMA_VERSION` et gerer la migration dans `_migrate_if_needed()`

---

## Deploiement (systemd)

```bash
sudo cp discord-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable discord-bot
sudo systemctl start discord-bot

# Consulter les logs
sudo journalctl -u discord-bot -f
```

---

## Depannage

| Probleme | Solution |
|---|---|
| Les commandes ne repondent pas | Verifier `DISCORD_TOKEN` dans `.env` et l'intent `message_content` |
| Donnees non sauvegardees | Verifier les permissions du dossier `data/` et l'espace disque |
| Bot silencieux | Verifier les permissions Discord (lire/envoyer des messages) |
| Reset complet des donnees | Arreter le bot, supprimer les fichiers JSON dans `data/` et a la racine, relancer |

---

## Dependances

| Package | Version | Role |
|---|---|---|
| discord.py | >= 2.4.0 | Framework Discord |
| python-dotenv | >= 1.0.0 | Lecture du `.env` |
| pytz | >= 2024.1 | Timezone Europe/Paris |

---

Projet prive — Tous droits reserves.

Cree pour la communaute Onyx. Derniere mise a jour : fevrier 2026.
