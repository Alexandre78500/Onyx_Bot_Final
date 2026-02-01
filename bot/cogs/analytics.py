import asyncio
import json
import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from discord import Reaction, User, Member
from discord.ext import commands, tasks


# Configuration
ANALYTICS_FILE = "data/analytics_v1.json"
ARCHIVE_FILE = "data/messages_archive_v1.jsonl"
CONFIG_FILE = "data/analytics_config.json"
SAVE_INTERVAL_MINUTES = 5
ARCHIVE_BUFFER_SIZE = 100

# Mots courants à exclure du word count
COMMON_WORDS = {
    "le", "la", "les", "un", "une", "des", "de", "du", "des", "et", "ou", "mais",
    "donc", "car", "ni", "que", "qui", "quoi", "dont", "où", "ce", "cet", "cette",
    "ces", "mon", "ton", "son", "ma", "ta", "sa", "mes", "tes", "ses", "notre",
    "votre", "leur", "nos", "vos", "leurs", "je", "tu", "il", "elle", "on", "nous",
    "vous", "ils", "elles", "me", "te", "se", "lui", "soi", "en", "y", "à", "dans",
    "par", "pour", "avec", "sans", "sur", "sous", "entre", "devant", "derrière",
    "l", "d", "s", "n", "c", "j", "m", "t", "est", "ai", "as", "a", "avons", "avez",
    "ont", "été", "être", "avoir", "faire", "plus", "moins", "très", "trop", "peu",
    "bien", "mal", "oui", "non", "si", "pas", "ne", "au", "aux", "ça", "ca"
}

CURRENT_SCHEMA_VERSION = 1


class AnalyticsCog(commands.Cog):
    """
    Cog d'analytics complet - Collecte toutes les données d'activité du serveur.
    """
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.data: Dict[str, Any] = {}
        self.archive_buffer: List[Dict] = []
        self.last_save: Optional[datetime] = None
        
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
                print(f"[Analytics] Données chargées - Schema v{self.data['_meta']['schema_version']}")
            except Exception as e:
                print(f"[Analytics] Erreur chargement: {e}")
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
                "guilds": {}
            },
            "_schema_history": []
        }
        self._save_data()
    
    def _migrate_if_needed(self):
        """Migre les données vers la dernière version du schéma."""
        current_version = self.data.get("_meta", {}).get("schema_version", 0)
        
        if current_version < CURRENT_SCHEMA_VERSION:
            print(f"[Analytics] Migration v{current_version} → v{CURRENT_SCHEMA_VERSION}")
            
            # Migration v0 → v1 (structure initiale)
            if current_version < 1:
                for guild_id in self.data.get("_meta", {}).get("guilds", {}):
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
            print(f"[Analytics] Migration terminée")
    
    def _create_empty_guild_stats(self) -> Dict:
        """Crée une structure de stats vide pour un serveur."""
        return {
            "global_stats": {
                "messages_total": 0,
                "messages_by_day": [0] * 7,  # Lundi=0, Dimanche=6
                "messages_by_hour": [0] * 24,  # 00h-23h
                "unique_users": [],
                "unique_channels": [],
                "word_counts": {},
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
    
    def _get_guild_data(self, guild_id: str) -> Dict:
        """Récupère ou crée les données d'un serveur."""
        if guild_id not in self.data:
            self.data[guild_id] = self._create_empty_guild_stats()
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
        
        # Récupérer les données du serveur
        guild_data = self._get_guild_data(guild_id)
        stats = guild_data["global_stats"]
        
        # 1. Stats temporelles
        stats["messages_total"] += 1
        stats["messages_by_day"][now.weekday()] += 1
        stats["messages_by_hour"][now.hour] += 1
        
        # 2. Utilisateurs uniques
        if author_id not in stats["unique_users"]:
            stats["unique_users"].append(author_id)
        
        # 3. Canaux uniques
        if channel_id not in stats["unique_channels"]:
            stats["unique_channels"].append(channel_id)
        
        # 4. Word count
        if message.content:
            words = self._extract_words(message.content)
            for word in words:
                if word not in COMMON_WORDS and len(word) >= 3:
                    stats["word_counts"][word] = stats["word_counts"].get(word, 0) + 1
        
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
        
        # 6. Détecter les conversations (réponse à un message récent)
        await self._detect_conversation(message, guild_data, author_id)
        
        # 7. Archiver le message
        self._archive_message(message, guild_id)
    
    def _extract_words(self, text: str) -> List[str]:
        """Extrait les mots d'un texte (minuscules, sans ponctuation)."""
        # Convertir en minuscules
        text = text.lower()
        
        # Remplacer la ponctuation par des espaces
        for char in ".,;:!?\"'()[]{}@#&-_=+/*$%":
            text = text.replace(char, " ")
        
        # Split et filtrer
        words = [w.strip() for w in text.split() if w.strip()]
        return words
    
    async def _detect_conversation(self, message, guild_data: Dict, author_id: str):
        """Détecte si le message est une réponse à quelqu'un (conversation)."""
        try:
            # Récupérer les 10 derniers messages du canal
            async for msg in message.channel.history(limit=10, before=message):
                if msg.author.id != message.author.id and not msg.author.bot:
                    # Si message dans les 5 dernières minutes = conversation
                    time_diff = (message.created_at - msg.created_at).total_seconds()
                    if time_diff <= 300:  # 5 minutes
                        other_id = str(msg.author.id)
                        
                        # Clé unique pour la paire (ordre alphabétique pour éviter doublons)
                        pair_key = "_".join(sorted([author_id, other_id]))
                        
                        stats = guild_data["global_stats"]
                        stats["conversations"][pair_key] = stats["conversations"].get(pair_key, 0) + 1
                        break  # On ne compte que la première réponse
        except:
            pass  # Silencieux si pas de permission ou erreur
    
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
            self._save_data()
            await self._flush_archive()
            self.last_save = datetime.now()
            print(f"[Analytics] Sauvegarde effectuée à {self.last_save}")
        except Exception as e:
            print(f"[Analytics] Erreur sauvegarde: {e}")
    
    def _save_data(self):
        """Sauvegarde les données analytics dans le fichier JSON."""
        try:
            with open(ANALYTICS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[Analytics] Erreur écriture JSON: {e}")
    
    async def _flush_archive(self):
        """Flush le buffer d'archive vers le fichier JSONL."""
        if not self.archive_buffer:
            return
        
        try:
            with open(ARCHIVE_FILE, 'a', encoding='utf-8') as f:
                for entry in self.archive_buffer:
                    f.write(json.dumps(entry, ensure_ascii=False) + '\n')
            
            print(f"[Analytics] {len(self.archive_buffer)} messages archivés")
            self.archive_buffer.clear()
        except Exception as e:
            print(f"[Analytics] Erreur flush archive: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(AnalyticsCog(bot))
