import asyncio
import json
import logging
import os
import random
from datetime import date, datetime, time
from typing import Dict, Tuple

import pytz
from discord.ext import commands, tasks

from bot.constants import GM_RESET_TIME, GM_SAVE_INTERVAL_SECONDS

# Fuseau horaire France
PARIS_TZ = pytz.timezone('Europe/Paris')

# Heure de reset (5h30 du matin)
RESET_TIME = GM_RESET_TIME

# Fichier de sauvegarde
DATA_FILE = "gm_data.json"
SAVE_INTERVAL_SECONDS = GM_SAVE_INTERVAL_SECONDS  # Sauvegarde toutes les 60s max

# Réponses personnalisées avec placeholder {pseudo}
GM_RESPONSES = [
    "Bonne matinée {pseudo}! ☀️",
    "Yo {pseudo}! gm 👋",
    "{pseudo}, belle journée à venir! ✨",
    "Salut {pseudo}! gm 🌅",
    "{pseudo}! Qui d'autre est réveillé? 💪",
    "gm {pseudo}! ☕ Belle matinée !",
    "{pseudo}! Prêt pour une nouvelle journée? 🚀",
    "Yo {pseudo}! gm et bon courage pour aujourd'hui! 💫",
]

logger = logging.getLogger(__name__)


class GMCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Structure: {guild_id: {user_id: (date, has_gm_been_said)}}
        self.gm_tracker: Dict[int, Dict[int, Tuple[date, bool]]] = {}
        self._dirty = False  # Flag: True si données modifiées depuis dernière sauvegarde
        self._load_data()
        self.periodic_save.start()  # Démarrer la sauvegarde périodique
    
    def cog_unload(self):
        self.periodic_save.cancel()
        # Sauvegarder à la fermeture
        if self._dirty:
            self._save_data_sync()
    
    def _load_data(self):
        """Charge les données GM depuis le fichier JSON."""
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Convertir les dates string en objets date
                    for guild_id_str, users in data.items():
                        guild_id = int(guild_id_str)
                        self.gm_tracker[guild_id] = {}
                        for user_id_str, entry in users.items():
                            if not isinstance(entry, (list, tuple)) or len(entry) != 2:
                                continue
                            date_str, has_said = entry
                            user_id = int(user_id_str)
                            date_obj = self._parse_date(date_str)
                            if date_obj is None:
                                continue
                            self.gm_tracker[guild_id][user_id] = (date_obj, bool(has_said))
            except Exception as e:
                logger.error(f"[GM] Erreur lors du chargement des données: {e}")
                self.gm_tracker = {}
    
    def _save_data_sync(self):
        """Sauvegarde synchrone des données (utilisée au shutdown)."""
        try:
            # Convertir les dates en string pour JSON
            data = {}
            for guild_id, users in self.gm_tracker.items():
                data[str(guild_id)] = {}
                for user_id, (date_obj, has_said) in users.items():
                    data[str(guild_id)][str(user_id)] = (self._serialize_date(date_obj), bool(has_said))
            
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            self._dirty = False
            logger.info("[GM] Données sauvegardées")
        except Exception as e:
            logger.error(f"[GM] Erreur lors de la sauvegarde: {e}")
    
    async def _save_data_async(self):
        """Sauvegarde asynchrone via executor."""
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._save_data_sync)
        except Exception as e:
            logger.error(f"[GM] Erreur sauvegarde async: {e}")
    
    @tasks.loop(seconds=SAVE_INTERVAL_SECONDS)
    async def periodic_save(self):
        """Sauvegarde périodique si données modifiées."""
        if self._dirty:
            await self._save_data_async()
    
    @periodic_save.before_loop
    async def before_periodic_save(self):
        await self.bot.wait_until_ready()
    
    def _get_current_datetime(self) -> datetime:
        """Retourne la date/heure actuelle en timezone Paris."""
        return datetime.now(PARIS_TZ)

    def _parse_date(self, date_str: str) -> date | None:
        """Parse une date YYYY-MM-DD, retourne None si invalide."""
        if not isinstance(date_str, str):
            return None
        try:
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return None

    def _serialize_date(self, date_obj: date) -> str:
        """Serialize une date en YYYY-MM-DD."""
        return date_obj.strftime('%Y-%m-%d')
    
    def _should_reset_for_user(self, guild_id: int, user_id: int) -> bool:
        """Vérifie si on doit réinitialiser pour cet utilisateur sur ce serveur."""
        if guild_id not in self.gm_tracker:
            return True
        
        if user_id not in self.gm_tracker[guild_id]:
            return True
        
        last_date, _ = self.gm_tracker[guild_id][user_id]
        now = self._get_current_datetime()
        current_date = now.date()
        current_time = now.time()
        
        # Réinitialiser si:
        # 1. La date a changé ET il est 5h30 ou plus
        # 2. Ou si on est sur un nouveau jour
        if current_date != last_date:
            if current_time >= RESET_TIME:
                return True
            # Si on est avant 5h30, on garde l'ancienne date (reset pas encore fait)
            return False
        
        return False
    
    def _reset_if_needed(self, guild_id: int, user_id: int):
        """Réinitialise l'état si nécessaire pour cet utilisateur."""
        if self._should_reset_for_user(guild_id, user_id):
            now = self._get_current_datetime()
            if guild_id not in self.gm_tracker:
                self.gm_tracker[guild_id] = {}
            self.gm_tracker[guild_id][user_id] = (now.date(), False)
            self._dirty = True
    
    def _has_gm_been_said(self, guild_id: int, user_id: int) -> bool:
        """Vérifie si cet utilisateur a déjà dit GM aujourd'hui sur ce serveur."""
        if guild_id not in self.gm_tracker:
            return False
        if user_id not in self.gm_tracker[guild_id]:
            return False
        _, has_said = self.gm_tracker[guild_id][user_id]
        return has_said
    
    def _mark_gm_said(self, guild_id: int, user_id: int):
        """Marque GM comme dit pour cet utilisateur sur ce serveur."""
        now = self._get_current_datetime()
        if guild_id not in self.gm_tracker:
            self.gm_tracker[guild_id] = {}
        self.gm_tracker[guild_id][user_id] = (now.date(), True)
        self._dirty = True
    
    @commands.Cog.listener()
    async def on_message(self, message):
        # Ignorer les messages du bot
        if message.author.bot:
            return
        
        # Ignorer les messages privés (pas de guild)
        if not message.guild:
            return
        
        guild_id = message.guild.id
        user_id = message.author.id
        
        # Réinitialiser si nécessaire (après 5h30)
        self._reset_if_needed(guild_id, user_id)
        
        # Vérifier si le message commence par "gm" (insensible à la casse)
        if not message.content.lower().startswith("gm"):
            return
        
        # Vérifier si cet utilisateur a déjà dit GM aujourd'hui sur ce serveur
        if self._has_gm_been_said(guild_id, user_id):
            return
        
        # Marquer GM comme dit pour cet utilisateur
        self._mark_gm_said(guild_id, user_id)
        
        # Récupérer le pseudo (nickname serveur sinon username)
        display_name = message.author.display_name
        
        # Choisir une réponse aléatoire et remplacer {pseudo}
        response_template = random.choice(GM_RESPONSES)
        response = response_template.format(pseudo=display_name)
        
        # Envoyer la réponse
        await message.channel.send(response, delete_after=60)


async def setup(bot: commands.Bot):
    await bot.add_cog(GMCog(bot))
