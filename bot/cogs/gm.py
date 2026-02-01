import asyncio
import random
from datetime import datetime, time

import pytz
from discord.ext import commands

# Fuseau horaire France
PARIS_TZ = pytz.timezone('Europe/Paris')

# Heures de début et fin (5h30 à 12h00)
START_TIME = time(5, 30)
END_TIME = time(12, 0)

# Réponses possibles du bot
GM_RESPONSES = [
    "gm ✨",
    "gm! ☀️",
    "gm tout le monde! 🌅",
    "Bonne matinée! gm ☕",
    "gm! Qui d'autre est réveillé? 👋",
    "gm! Belle journée à venir! 🌟",
]


class GMCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.gm_said_today = False
        self.current_date = None

    def _is_gm_time(self) -> bool:
        """Vérifie si on est dans la plage horaire GM (5h30-12h)."""
        now = datetime.now(PARIS_TZ)
        current_time = now.time()
        return START_TIME <= current_time <= END_TIME

    def _reset_daily_state(self):
        """Réinitialise l'état quotidien si on est sur un nouveau jour."""
        now = datetime.now(PARIS_TZ)
        today = now.date()
        
        if self.current_date != today:
            self.current_date = today
            self.gm_said_today = False

    @commands.Cog.listener()
    async def on_message(self, message):
        # Ignorer les messages du bot
        if message.author.bot:
            return
        
        # Réinitialiser l'état si nouveau jour
        self._reset_daily_state()
        
        # Vérifier si c'est l'heure du GM
        if not self._is_gm_time():
            return
        
        # Vérifier si le message commence par "gm" (insensible à la casse)
        if not message.content.lower().startswith("gm"):
            return
        
        # Vérifier si GM a déjà été dit aujourd'hui
        if self.gm_said_today:
            return
        
        # Marquer GM comme dit pour aujourd'hui
        self.gm_said_today = True
        
        # Attendre entre 5 et 10 secondes
        delay = random.randint(5, 10)
        await asyncio.sleep(delay)
        
        # Choisir une réponse aléatoire
        response = random.choice(GM_RESPONSES)
        
        # Envoyer la réponse
        await message.channel.send(response)


async def setup(bot: commands.Bot):
    await bot.add_cog(GMCog(bot))
