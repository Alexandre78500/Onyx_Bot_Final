import asyncio
import json
import logging
import os
import re
from collections import deque
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set

from discord import Reaction, User
from discord.ext import commands, tasks

from bot.constants import (
    ANALYTICS_ARCHIVE_BUFFER_SIZE,
    ANALYTICS_MESSAGE_CACHE_SIZE,
    ANALYTICS_MESSAGE_CACHE_TTL_SECONDS,
    ANALYTICS_SAVE_INTERVAL_MINUTES,
    ANALYTICS_WORD_COUNT_TOP_N,
    ANALYTICS_DEBUG_WORDS,
)

# Configuration
ANALYTICS_FILE = "data/analytics_v1.json"
ARCHIVE_FILE = "data/messages_archive_v1.jsonl"
CONFIG_FILE = "data/analytics_config.json"
SAVE_INTERVAL_MINUTES = ANALYTICS_SAVE_INTERVAL_MINUTES
ARCHIVE_BUFFER_SIZE = ANALYTICS_ARCHIVE_BUFFER_SIZE

# Mots courants à exclure du word count
COMMON_WORDS = {
    # Articles / déterminants
    "le", "la", "les", "un", "une", "des", "de", "du", "au", "aux",
    # Pronoms personnels / réfléchis
    "je", "tu", "il", "elle", "on", "nous", "vous", "ils", "elles",
    "me", "te", "se", "lui", "soi", "en", "y", "moi", "toi", "eux",
    # Pronoms démonstratifs / relatifs / interrogatifs
    "ce", "cet", "cette", "ces", "que", "qui", "quoi", "dont", "où",
    # Possessifs
    "mon", "ton", "son", "ma", "ta", "sa", "mes", "tes", "ses",
    "notre", "votre", "leur", "nos", "vos", "leurs",
    # Conjonctions
    "et", "ou", "mais", "donc", "car", "ni", "puis", "sinon",
    # Prépositions
    "à", "dans", "par", "pour", "avec", "sans", "sur", "sous",
    "entre", "devant", "derrière", "vers", "chez", "après", "avant",
    "pendant", "depuis", "contre", "jusque",
    # Adverbes courants
    "plus", "moins", "très", "trop", "peu", "bien", "mal",
    "aussi", "encore", "même", "tout", "tous", "toute", "toutes",
    "rien", "jamais", "toujours", "alors", "comme", "quand", "comment",
    "vraiment", "juste", "déjà", "assez", "tant", "tellement",
    "là", "ici", "maintenant", "peut", "être",
    # Verbes auxiliaires / très courants (conjugaisons)
    "est", "ai", "as", "a", "avons", "avez", "ont", "été", "être", "avoir",
    "faire", "fait", "fais", "dit", "dis", "suis", "était", "sont", "sera",
    "vais", "vas", "aller", "peux", "peut", "veut", "veux", "faut", "doit",
    "voit", "sait", "met", "mis",
    # Négation / affirmation
    "oui", "non", "si", "pas", "ne", "ça", "ca",
    # Fragments d'élision
    "l", "d", "s", "n", "c", "j", "m", "t", "qu",
    # Argot / mots informels Discord
    "mdr", "lol", "ptdr", "xd", "haha", "ahah", "hihi", "hehe",
    "osef", "tkt", "stp", "svp", "btw", "omg", "jsp", "jpp",
    "tmtc", "oklm", "fdp", "wtf", "imo", "afk", "gg", "wp",
}

CUSTOM_EMOJI_RE = re.compile(r"<a?:([A-Za-z0-9_]+):\d+>")
SHORTCODE_EMOJI_RE = re.compile(r":([A-Za-z0-9_]+):")
URL_RE = re.compile(r"https?://\S+")
MENTION_RE = re.compile(r"<[@#][!&]?\d+>")
REPEATED_CHAR_RE = re.compile(r"(.)\1{2,}")
UNICODE_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001F5FF"  # Misc Symbols and Pictographs
    "\U0001F600-\U0001F64F"  # Emoticons
    "\U0001F680-\U0001F6FF"  # Transport and Map
    "\U0001F700-\U0001F77F"  # Alchemical Symbols
    "\U0001F780-\U0001F7FF"  # Geometric Shapes Extended
    "\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
    "\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
    "\U0001FA00-\U0001FA6F"  # Chess Symbols
    "\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
    "\U00002700-\U000027BF"  # Dingbats
    "\U00002600-\U000026FF"  # Misc Symbols
    "\U0001F1E0-\U0001F1FF"  # Drapeaux (Regional Indicators)
    "\U0000FE00-\U0000FE0F"  # Variation Selectors
    "\U0000200D"             # Zero Width Joiner
    "\U00002300-\U000023FF"  # Misc Technical
    "\U00002B50-\U00002B55"  # Stars
    "\U000000A9"             # Copyright
    "\U000000AE"             # Registered
    "\U0000203C-\U00003299"  # Misc symbols CJK
    "]",
    re.UNICODE,
)

# Cache pour conversations: garde les 20 derniers messages par canal (max 10 min)
MESSAGE_CACHE_SIZE = ANALYTICS_MESSAGE_CACHE_SIZE
MESSAGE_CACHE_TTL_SECONDS = ANALYTICS_MESSAGE_CACHE_TTL_SECONDS

CURRENT_SCHEMA_VERSION = 1
logger = logging.getLogger(__name__)


class AnalyticsCog(commands.Cog):
    """
    Cog d'analytics complet - Collecte toutes les données d'activité du serveur.
    """
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.data: Dict[str, Any] = {}
        self.archive_buffer: List[Dict] = []
        self.last_save: Optional[datetime] = None
        
        # Cache mémoire pour conversations: {channel_id: deque[(author_id, timestamp), ...]}
        self.message_cache: Dict[str, deque] = {}
        
        # Sets pour utilisateurs/canaux uniques (recherche O(1) vs O(n) avec liste)
        self._unique_users_cache: Dict[str, Set[str]] = {}
        self._unique_channels_cache: Dict[str, Set[str]] = {}
        
        # Créer le dossier data s'il n'existe pas
        os.makedirs("data", exist_ok=True)
        
        # Charger ou initialiser les données
        self._load_data()
        
        # Démarrer la sauvegarde périodique
        self.periodic_save.start()
    
    def cog_unload(self):
        """Appelé quand le cog est déchargé - force la sauvegarde."""
        self.periodic_save.cancel()
        asyncio.create_task(self._force_save())
    
    def _load_data(self):
        """Charge les données depuis le fichier JSON ou initialise."""
        if os.path.exists(ANALYTICS_FILE):
            try:
                with open(ANALYTICS_FILE, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
                
                # Vérifier et migrer si nécessaire
                self._migrate_if_needed()
                logger.info(f"[Analytics] Données chargées - Schema v{self.data['_meta']['schema_version']}")
            except Exception as e:
                logger.error(f"[Analytics] Erreur chargement: {e}")
                self._init_empty_data()
        else:
            self._init_empty_data()
    
    def _init_empty_data(self):
        """Initialise une structure de données vide."""
        self.data = {
            "_meta": {
                "schema_version": CURRENT_SCHEMA_VERSION,
                "created_at": datetime.now().isoformat(),
                "last_migration": datetime.now().isoformat(),
                "guilds": {},
                "last_word_prune": None
            },
            "_schema_history": []
        }
        self._save_data()
    
    def _migrate_if_needed(self):
        """Migre les données vers la dernière version du schéma."""
        current_version = self.data.get("_meta", {}).get("schema_version", 0)
        
        if current_version < CURRENT_SCHEMA_VERSION:
            logger.info(f"[Analytics] Migration v{current_version} → v{CURRENT_SCHEMA_VERSION}")
            
            # Migration v0 → v1 (structure initiale)
            if current_version < 1:
                meta_guilds = self.data.get("_meta", {}).get("guilds", [])
                if isinstance(meta_guilds, dict):
                    meta_guilds = list(meta_guilds)
                elif not isinstance(meta_guilds, list):
                    meta_guilds = []

                # Prioriser les guilds déjà présentes dans les données
                guild_ids = [key for key in self.data.keys() if not key.startswith("_")]
                if not guild_ids:
                    guild_ids = meta_guilds

                for guild_id in guild_ids:
                    if guild_id not in self.data:
                        self.data[guild_id] = self._create_empty_guild_stats()
            
            # Mettre à jour la version
            self.data["_meta"]["schema_version"] = CURRENT_SCHEMA_VERSION
            self.data["_meta"]["last_migration"] = datetime.now().isoformat()
            self.data["_schema_history"].append({
                "from_version": current_version,
                "to_version": CURRENT_SCHEMA_VERSION,
                "date": datetime.now().isoformat(),
                "changes": ["Initial schema setup"]
            })
            
            self._save_data()
            logger.info("[Analytics] Migration terminée")
    
    def _create_empty_guild_stats(self) -> Dict:
        """Crée une structure de stats vide pour un serveur."""
        return {
            "global_stats": {
                "messages_total": 0,
                "messages_by_day": [0] * 7,  # Lundi=0, Dimanche=6
                "messages_by_hour": [0] * 24,  # 00h-23h
                "messages_by_segment": {
                    "night": 0,
                    "morning": 0,
                    "afternoon": 0,
                    "evening": 0
                },
                "messages_by_segment_by_user": {},
                "unique_users": [],  # Stocké comme liste pour JSON, mais on utilise des sets en mémoire
                "unique_channels": [],
                "word_counts": {},
                "word_counts_by_user": {},
                "emoji_text_usage": {
                    "users": {}
                },
                "conversations": {},  # "userA_userB": count
                "mentions_graph": {
                    "given": {},  # user: {target: count}
                    "received": {}  # user: {source: count}
                },
                "reactions_stats": {
                    "total_added": 0,
                    "by_emoji": {}
                }
            },
            "daily_snapshots": []
        }
    
    def _init_cache_for_guild(self, guild_id: str):
        """Initialise les caches en mémoire pour un serveur."""
        if guild_id not in self._unique_users_cache:
            self._unique_users_cache[guild_id] = set()
        if guild_id not in self._unique_channels_cache:
            self._unique_channels_cache[guild_id] = set()
    
    def _update_message_cache(self, channel_id: str, author_id: str, timestamp: datetime):
        """Met à jour le cache de messages pour un canal."""
        if channel_id not in self.message_cache:
            self.message_cache[channel_id] = deque(maxlen=MESSAGE_CACHE_SIZE)
        
        # Nettoyer les anciens messages (> 10 min) du cache
        cutoff = timestamp - timedelta(seconds=MESSAGE_CACHE_TTL_SECONDS)
        cache = self.message_cache[channel_id]
        while cache and cache[0][1] < cutoff:
            cache.popleft()
        
        # Ajouter le nouveau message
        cache.append((author_id, timestamp))
    
    def _get_guild_data(self, guild_id: str) -> Dict:
        """Récupère ou crée les données d'un serveur."""
        if guild_id not in self.data:
            self.data[guild_id] = self._create_empty_guild_stats()
            self._init_cache_for_guild(guild_id)
        
        # Synchroniser les sets mémoire avec les données JSON si premier accès
        if guild_id not in self._unique_users_cache:
            stats = self.data[guild_id]["global_stats"]
            self._unique_users_cache[guild_id] = set(stats.get("unique_users", []))
            self._unique_channels_cache[guild_id] = set(stats.get("unique_channels", []))
        
        return self.data[guild_id]
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Collecte les données à chaque message."""
        # Ignorer les bots
        if message.author.bot:
            return
        
        # Ignorer les DM
        if not message.guild:
            return
        
        guild_id = str(message.guild.id)
        author_id = str(message.author.id)
        channel_id = str(message.channel.id)
        now = datetime.now()
        msg_timestamp = message.created_at.replace(tzinfo=None) if message.created_at.tzinfo else message.created_at
        
        # Récupérer les données du serveur
        guild_data = self._get_guild_data(guild_id)
        stats = guild_data["global_stats"]
        
        # 1. Stats temporelles
        stats["messages_total"] += 1
        stats["messages_by_day"][now.weekday()] += 1
        stats["messages_by_hour"][now.hour] += 1
        if "messages_by_segment" not in stats:
            stats["messages_by_segment"] = {"night": 0, "morning": 0, "afternoon": 0, "evening": 0}
        segment = self._get_time_segment(now.hour)
        stats["messages_by_segment"][segment] = stats["messages_by_segment"].get(segment, 0) + 1
        user_segments = stats.setdefault("messages_by_segment_by_user", {}).setdefault(
            author_id,
            {"night": 0, "morning": 0, "afternoon": 0, "evening": 0},
        )
        user_segments[segment] = user_segments.get(segment, 0) + 1
        
        # 2. Utilisateurs uniques (utilisation de set pour O(1))
        if author_id not in self._unique_users_cache[guild_id]:
            self._unique_users_cache[guild_id].add(author_id)
            stats["unique_users"].append(author_id)
        
        # 3. Canaux uniques (utilisation de set pour O(1))
        if channel_id not in self._unique_channels_cache[guild_id]:
            self._unique_channels_cache[guild_id].add(channel_id)
            stats["unique_channels"].append(channel_id)
        
        # 4. Word count
        if message.content and not message.content.startswith(("o!", "O!", "!", "?", ".", "/", "$", "~", "-", "+")):
            words = self._extract_words(message.content)
            kept_words = [
                word for word in words
                if word not in COMMON_WORDS
                and len(word) >= 3
                and not word.isdigit()
                and not REPEATED_CHAR_RE.fullmatch(word)
            ]
            if kept_words:
                for word in kept_words:
                    stats["word_counts"][word] = stats["word_counts"].get(word, 0) + 1
                user_words = stats.setdefault("word_counts_by_user", {}).setdefault(author_id, {})
                for word in kept_words:
                    user_words[word] = user_words.get(word, 0) + 1
            if ANALYTICS_DEBUG_WORDS and kept_words:
                logger.debug(
                    "[Analytics] Words kept guild=%s author=%s words=%s",
                    guild_id,
                    author_id,
                    kept_words,
                )
                try:
                    await message.channel.send(
                        f"[Debug mots] {', '.join(kept_words)}"
                    )
                except Exception:
                    pass

        # 4b. Emojis texte (par utilisateur)
        if message.content:
            emojis = self._extract_text_emojis(message.content)
            if emojis:
                if "emoji_text_usage" not in stats:
                    stats["emoji_text_usage"] = {"users": {}}
                user_emojis = stats["emoji_text_usage"]["users"].setdefault(author_id, {})
                for emoji in emojis:
                    user_emojis[emoji] = user_emojis.get(emoji, 0) + 1
        
        # 5. Mentions
        if message.mentions:
            for mentioned in message.mentions:
                if not mentioned.bot:  # Ignorer les bots mentionnés
                    mentioned_id = str(mentioned.id)
                    
                    # Given (l'auteur mentionne)
                    if author_id not in stats["mentions_graph"]["given"]:
                        stats["mentions_graph"]["given"][author_id] = {}
                    stats["mentions_graph"]["given"][author_id][mentioned_id] = \
                        stats["mentions_graph"]["given"][author_id].get(mentioned_id, 0) + 1
                    
                    # Received (la personne est mentionnée)
                    if mentioned_id not in stats["mentions_graph"]["received"]:
                        stats["mentions_graph"]["received"][mentioned_id] = {}
                    stats["mentions_graph"]["received"][mentioned_id][author_id] = \
                        stats["mentions_graph"]["received"][mentioned_id].get(author_id, 0) + 1
        
        # 6. Mettre à jour le cache de messages
        self._update_message_cache(channel_id, author_id, msg_timestamp)
        
        # 7. Détecter les conversations via le cache (sans appel API)
        self._detect_conversation(message, guild_data, author_id, channel_id, msg_timestamp)
        
        # 8. Archiver le message
        self._archive_message(message, guild_id)
    
    def _extract_words(self, text: str) -> List[str]:
        """Extrait les mots d'un texte (minuscules, sans ponctuation)."""
        # Convertir en minuscules
        text = text.lower()

        # Retirer liens, mentions et emojis
        text = URL_RE.sub(" ", text)
        text = MENTION_RE.sub(" ", text)
        text = CUSTOM_EMOJI_RE.sub(" ", text)
        text = SHORTCODE_EMOJI_RE.sub(" ", text)
        text = UNICODE_EMOJI_RE.sub(" ", text)
        
        # Remplacer la ponctuation par des espaces
        for char in ".,;:!?\"'()[]{}@#&-_=+/*$%~`^|<>\\":
            text = text.replace(char, " ")
        
        # Split et filtrer
        words = [w.strip() for w in text.split() if w.strip()]
        return words

    def _get_time_segment(self, hour: int) -> str:
        """Retourne la tranche horaire (night, morning, afternoon, evening)."""
        if 0 <= hour <= 5:
            return "night"
        if 6 <= hour <= 11:
            return "morning"
        if 12 <= hour <= 17:
            return "afternoon"
        return "evening"

    def _extract_text_emojis(self, text: str) -> List[str]:
        """Extrait les emojis du texte (unicode + custom)."""
        emojis: List[str] = []
        if not text:
            return emojis

        for name in CUSTOM_EMOJI_RE.findall(text):
            emojis.append(f":{name}:")

        emojis.extend(UNICODE_EMOJI_RE.findall(text))
        return emojis
    
    def _detect_conversation(self, message, guild_data: Dict, author_id: str, channel_id: str, timestamp: datetime):
        """Détecte si le message est une réponse (référence si dispo, sinon cache)."""
        reference = getattr(message, "reference", None)
        resolved = getattr(reference, "resolved", None) if reference else None
        if resolved and getattr(resolved, "author", None):
            ref_author_id = str(resolved.author.id)
            if ref_author_id != author_id and not resolved.author.bot:
                ref_timestamp = resolved.created_at.replace(tzinfo=None) if resolved.created_at.tzinfo else resolved.created_at
                time_diff = (timestamp - ref_timestamp).total_seconds()
                if 0 <= time_diff <= 300:
                    pair_key = "_".join(sorted([author_id, ref_author_id]))
                    stats = guild_data["global_stats"]
                    stats["conversations"][pair_key] = stats["conversations"].get(pair_key, 0) + 1
                    return

        # Fallback: cache mémoire
        cache = self.message_cache.get(channel_id)
        if not cache:
            return
        
        # Parcourir le cache à l'envers pour trouver le dernier message d'un autre auteur
        for cached_author_id, cached_timestamp in reversed(cache):
            # Ignorer ses propres messages
            if cached_author_id == author_id:
                continue
            
            # Vérifier si c'est dans les 5 dernières minutes
            time_diff = (timestamp - cached_timestamp).total_seconds()
            if 0 <= time_diff <= 300:  # 5 minutes
                # Clé unique pour la paire (ordre alphabétique pour éviter doublons)
                pair_key = "_".join(sorted([author_id, cached_author_id]))
                
                stats = guild_data["global_stats"]
                stats["conversations"][pair_key] = stats["conversations"].get(pair_key, 0) + 1
                break  # On ne compte que la première réponse
    
    def _archive_message(self, message, guild_id: str):
        """Ajoute le message à l'archive buffer."""
        archive_entry = {
            "ts": message.created_at.isoformat(),
            "guild": guild_id,
            "channel": str(message.channel.id),
            "author": str(message.author.id),
            "author_name": message.author.display_name,
            "content": message.content,
            "mentions": [str(m.id) for m in message.mentions if not m.bot],
            "has_attachments": len(message.attachments) > 0,
            "is_reply_to": str(message.reference.message_id) if message.reference else None,
            "msg_id": str(message.id)
        }
        
        self.archive_buffer.append(archive_entry)
        
        # Flush si buffer plein
        if len(self.archive_buffer) >= ARCHIVE_BUFFER_SIZE:
            asyncio.create_task(self._flush_archive())

    def _prune_word_counts_if_needed(self):
        """Garde uniquement le top N des mots une fois par jour."""
        today = datetime.now().date().isoformat()
        last_prune = self.data.get("_meta", {}).get("last_word_prune")
        if last_prune == today:
            return

        for guild_id, guild_data in self.data.items():
            if guild_id.startswith("_"):
                continue
            stats = guild_data.get("global_stats", {})
            word_counts = stats.get("word_counts", {})
            if word_counts:
                # Trier par occurrences (desc), puis par mot (asc) pour stabilite
                top_items = sorted(word_counts.items(), key=lambda item: (-item[1], item[0]))
                top_items = top_items[:ANALYTICS_WORD_COUNT_TOP_N]
                stats["word_counts"] = {word: count for word, count in top_items}

            word_counts_by_user = stats.get("word_counts_by_user", {})
            if word_counts_by_user:
                for user_id, counts in list(word_counts_by_user.items()):
                    if not counts:
                        continue
                    top_items = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
                    top_items = top_items[:ANALYTICS_WORD_COUNT_TOP_N]
                    word_counts_by_user[user_id] = {word: count for word, count in top_items}

        self.data["_meta"]["last_word_prune"] = today
    
    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: Reaction, user: User):
        """Collecte les stats sur les réactions."""
        if user.bot:
            return
        
        if not reaction.message.guild:
            return
        
        guild_id = str(reaction.message.guild.id)
        guild_data = self._get_guild_data(guild_id)
        stats = guild_data["global_stats"]["reactions_stats"]
        
        # Compter la réaction
        stats["total_added"] += 1
        
        # Identifier l'emoji
        emoji_str = str(reaction.emoji)
        if hasattr(reaction.emoji, 'name'):
            emoji_str = reaction.emoji.name  # Emoji personnalisé
        
        stats["by_emoji"][emoji_str] = stats["by_emoji"].get(emoji_str, 0) + 1
    
    @tasks.loop(minutes=SAVE_INTERVAL_MINUTES)
    async def periodic_save(self):
        """Sauvegarde périodique des données."""
        await self._force_save()
    
    @periodic_save.before_loop
    async def before_periodic_save(self):
        """Attendre que le bot soit prêt."""
        await self.bot.wait_until_ready()
    
    async def _force_save(self):
        """Force la sauvegarde immédiate des données."""
        try:
            self._prune_word_counts_if_needed()
            await self._save_data_async()
            await self._flush_archive()
            self.last_save = datetime.now()
            logger.info(f"[Analytics] Sauvegarde effectuée à {self.last_save}")
        except Exception as e:
            logger.error(f"[Analytics] Erreur sauvegarde: {e}")
    
    def _save_data(self):
        """Sauvegarde synchrone des données (pour shutdown)."""
        try:
            with open(ANALYTICS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[Analytics] Erreur écriture JSON: {e}")
    
    async def _save_data_async(self):
        """Sauvegarde asynchrone des données dans un executor pour ne pas bloquer."""
        try:
            # Utiliser run_in_executor pour ne pas bloquer l'event loop
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._save_data)
        except Exception as e:
            logger.error(f"[Analytics] Erreur sauvegarde async: {e}")
    
    async def _flush_archive(self):
        """Flush le buffer d'archive vers le fichier JSONL."""
        if not self.archive_buffer:
            return
        
        # Copier le buffer pour éviter les modifications pendant l'écriture
        buffer_to_flush = self.archive_buffer.copy()
        self.archive_buffer.clear()
        
        try:
            # Utiliser run_in_executor pour l'I/O fichier
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._write_archive_sync, buffer_to_flush)
            logger.info(f"[Analytics] {len(buffer_to_flush)} messages archivés")
        except Exception as e:
            logger.error(f"[Analytics] Erreur flush archive: {e}")
            # Remettre les messages dans le buffer en cas d'erreur
            self.archive_buffer.extend(buffer_to_flush)
    
    def _write_archive_sync(self, buffer: List[Dict]):
        """Écriture synchrone de l'archive (appelée dans un executor)."""
        with open(ARCHIVE_FILE, 'a', encoding='utf-8') as f:
            for entry in buffer:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')


async def setup(bot: commands.Bot):
    await bot.add_cog(AnalyticsCog(bot))
