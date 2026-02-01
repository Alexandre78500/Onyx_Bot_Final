import asyncio
import random
from datetime import datetime, time

import pytz
from discord.ext import commands

# Fuseau horaire France
PARIS_TZ = pytz.timezone('Europe/Paris')

# Heure de reset (5h30 du matin)
RESET_TIME = time(5, 30)

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


class GMCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Structure: {guild_id: {user_id: (date, has_gm_been_said)}}
        self.gm_tracker = {}

    def _get_current_datetime(self) -> datetime:
        """Retourne la date/heure actuelle en timezone Paris."""
        return datetime.now(PARIS_TZ)

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
        
        # Attendre entre 5 et 10 secondes
        delay = random.randint(5, 10)
        await asyncio.sleep(delay)
        
        # Récupérer le pseudo (nickname serveur sinon username)
        display_name = message.author.display_name
        
        # Choisir une réponse aléatoire et remplacer {pseudo}
        response_template = random.choice(GM_RESPONSES)
        response = response_template.format(pseudo=display_name)
        
        # Envoyer la réponse
        await message.channel.send(response)


async def setup(bot: commands.Bot):
    await bot.add_cog(GMCog(bot))
