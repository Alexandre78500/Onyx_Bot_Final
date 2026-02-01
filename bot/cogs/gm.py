import asyncio
import random
from datetime import datetime, time

import pytz
from discord.ext import commands

# Fuseau horaire France
PARIS_TZ = pytz.timezone('Europe/Paris')

# Heure de reset (5h30 du matin)
RESET_TIME = time(5, 30)

# Réponses possibles du bot
GM_RESPONSES = [
    "gm ✨",
    "gm! ☀️",
    "gm tout le monde! 🌅",
    "Bonne matinée! gm ☕",
    "gm! Qui d'autre est réveillé? 👋",
    "gm! Belle journée à venir! 🌟",
    "Yo! gm 👊",
    "gm, l'équipe! 💪",
]


class GMCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Dictionnaire pour tracker par serveur: {guild_id: (date, has_gm_been_said)}
        self.gm_tracker = {}

    def _get_current_datetime(self) -> datetime:
        """Retourne la date/heure actuelle en timezone Paris."""
        return datetime.now(PARIS_TZ)

    def _should_reset(self, guild_id: int) -> bool:
        """Vérifie si on doit réinitialiser pour ce serveur (après 5h30)."""
        if guild_id not in self.gm_tracker:
            return True
        
        last_date, _ = self.gm_tracker[guild_id]
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

    def _reset_if_needed(self, guild_id: int):
        """Réinitialise l'état si nécessaire pour ce serveur."""
        if self._should_reset(guild_id):
            now = self._get_current_datetime()
            self.gm_tracker[guild_id] = (now.date(), False)

    def _has_gm_been_said(self, guild_id: int) -> bool:
        """Vérifie si GM a déjà été dit aujourd'hui sur ce serveur."""
        if guild_id not in self.gm_tracker:
            return False
        _, has_said = self.gm_tracker[guild_id]
        return has_said

    def _mark_gm_said(self, guild_id: int):
        """Marque GM comme dit pour aujourd'hui sur ce serveur."""
        now = self._get_current_datetime()
        self.gm_tracker[guild_id] = (now.date(), True)

    @commands.Cog.listener()
    async def on_message(self, message):
        # Ignorer les messages du bot
        if message.author.bot:
            return
        
        # Ignorer les messages privés (pas de guild)
        if not message.guild:
            return
        
        guild_id = message.guild.id
        
        # Réinitialiser si nécessaire (après 5h30)
        self._reset_if_needed(guild_id)
        
        # Vérifier si le message commence par "gm" (insensible à la casse)
        if not message.content.lower().startswith("gm"):
            return
        
        # Vérifier si GM a déjà été dit aujourd'hui sur ce serveur
        if self._has_gm_been_said(guild_id):
            return
        
        # Marquer GM comme dit pour ce serveur
        self._mark_gm_said(guild_id)
        
        # Attendre entre 5 et 10 secondes
        delay = random.randint(5, 10)
        await asyncio.sleep(delay)
        
        # Choisir une réponse aléatoire
        response = random.choice(GM_RESPONSES)
        
        # Envoyer la réponse
        await message.channel.send(response)


async def setup(bot: commands.Bot):
    await bot.add_cog(GMCog(bot))
