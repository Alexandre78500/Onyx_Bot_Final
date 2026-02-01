import asyncio
import json
import os
import random
from datetime import datetime, time, timedelta

import pytz
from discord import Embed, Object, app_commands
from discord.ext import commands, tasks

# Configuration
PARIS_TZ = pytz.timezone('Europe/Paris')
DATA_FILE = "engagement_data.json"
COOLDOWN_SECONDS = 15  # Anti-spam: 15 secondes entre chaque comptabilisation
GENERAL_CHANNEL_ID = 376777553945296899  # Canal général

# Gains d'XP
XP_PER_MESSAGE_MIN = 5
XP_PER_MESSAGE_MAX = 15
XP_GM_BONUS = 50


def calculate_level(xp):
    """Calcule le niveau basé sur l'XP."""
    level = 1
    while xp >= 100 * (level ** 1.5):
        xp -= 100 * (level ** 1.5)
        level += 1
    return level


def get_level_progress(xp):
    """Retourne la progression dans le niveau actuel (0-100%)."""
    level = 1
    xp_remaining = xp
    while xp_remaining >= 100 * (level ** 1.5):
        xp_remaining -= 100 * (level ** 1.5)
        level += 1
    
    xp_for_next = 100 * (level ** 1.5)
    progress = (xp_remaining / xp_for_next) * 100
    return progress, level


class EngagementCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.data = {"users": {}, "weekly_reset": None}
        self.cooldowns = {}  # {user_id: last_message_time}
        self._load_data()
        self.weekly_ranking.start()
    
    def cog_unload(self):
        self.weekly_ranking.cancel()
    
    def _load_data(self):
        """Charge les données depuis le fichier JSON."""
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
                    # Convertir les dates
                    if self.data.get("weekly_reset"):
                        self.data["weekly_reset"] = datetime.fromisoformat(self.data["weekly_reset"])
            except Exception as e:
                print(f"Erreur chargement engagement: {e}")
                self.data = {"users": {}, "weekly_reset": None}
    
    def _save_data(self):
        """Sauvegarde les données dans le fichier JSON."""
        try:
            data_to_save = self.data.copy()
            if data_to_save.get("weekly_reset"):
                data_to_save["weekly_reset"] = data_to_save["weekly_reset"].isoformat()
            
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Erreur sauvegarde engagement: {e}")
    
    def _get_paris_now(self):
        """Retourne la datetime actuelle à Paris."""
        return datetime.now(PARIS_TZ)
    
    def _check_cooldown(self, user_id: int) -> bool:
        """Vérifie si l'utilisateur peut gagner de l'XP (cooldown 15s)."""
        now = self._get_paris_now()
        if user_id in self.cooldowns:
            last_time = self.cooldowns[user_id]
            if (now - last_time).total_seconds() < COOLDOWN_SECONDS:
                return False
        self.cooldowns[user_id] = now
        return True
    
    def _add_xp(self, user_id: int, xp_amount: int, is_weekly: bool = True):
        """Ajoute de l'XP à un utilisateur."""
        user_id_str = str(user_id)
        
        if user_id_str not in self.data["users"]:
            self.data["users"][user_id_str] = {
                "xp": 0,
                "weekly_xp": 0,
                "messages": 0,
                "last_active": None
            }
        
        user_data = self.data["users"][user_id_str]
        user_data["xp"] += xp_amount
        if is_weekly:
            user_data["weekly_xp"] += xp_amount
        user_data["messages"] += 1
        user_data["last_active"] = self._get_paris_now().isoformat()
        
        self._save_data()
        return user_data
    
    def _reset_weekly(self):
        """Reset les stats hebdomadaires."""
        for user_data in self.data["users"].values():
            user_data["weekly_xp"] = 0
        
        # Prochain reset: dimanche prochain à 20h
        now = self._get_paris_now()
        days_until_sunday = (6 - now.weekday()) % 7
        if days_until_sunday == 0:
            days_until_sunday = 7
        next_reset = now + timedelta(days=days_until_sunday)
        next_reset = next_reset.replace(hour=20, minute=0, second=0, microsecond=0)
        
        self.data["weekly_reset"] = next_reset
        self._save_data()
    
    @commands.Cog.listener()
    async def on_message(self, message):
        # Ignorer bot et DM
        if message.author.bot or not message.guild:
            return
        
        user_id = message.author.id
        
        # Vérifier cooldown anti-spam
        if not self._check_cooldown(user_id):
            return
        
        # Ajouter XP (5-15 aléatoire)
        xp_gain = random.randint(XP_PER_MESSAGE_MIN, XP_PER_MESSAGE_MAX)
        self._add_xp(user_id, xp_gain)
    
    @tasks.loop(minutes=1)
    async def weekly_ranking(self):
        """Poste le classement hebdomadaire le dimanche à 20h."""
        now = self._get_paris_now()
        
        # Vérifier si c'est le moment de poster
        if self.data.get("weekly_reset") and now >= self.data["weekly_reset"]:
            await self._post_ranking()
            self._reset_weekly()
    
    @weekly_ranking.before_loop
    async def before_weekly_ranking(self):
        await self.bot.wait_until_ready()
    
    async def _post_ranking(self):
        """Poste le classement dans le canal général."""
        channel = self.bot.get_channel(GENERAL_CHANNEL_ID)
        if not channel:
            print(f"Canal {GENERAL_CHANNEL_ID} non trouvé")
            return
        
        # Trier par XP hebdomadaire
        sorted_users = sorted(
            self.data["users"].items(),
            key=lambda x: x[1].get("weekly_xp", 0),
            reverse=True
        )[:10]  # Top 10
        
        if not sorted_users:
            return
        
        # Créer l'embed
        embed = Embed(
            title="🏆 Classement de la Semaine",
            description="Top 10 des membres les plus actifs cette semaine !",
            color=0xFFD700,
            timestamp=self._get_paris_now()
        )
        
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        
        for i, (user_id, data) in enumerate(sorted_users):
            user = self.bot.get_user(int(user_id))
            if not user:
                continue
            
            weekly_xp = data.get("weekly_xp", 0)
            total_xp = data.get("xp", 0)
            level = calculate_level(total_xp)
            
            medal = medals[i] if i < 10 else f"{i+1}."
            embed.add_field(
                name=f"{medal} {user.display_name}",
                value=f"Niveau {level} • {weekly_xp} XP cette semaine",
                inline=False
            )
        
        # Mention du gagnant
        winner_id = sorted_users[0][0]
        winner = self.bot.get_user(int(winner_id))
        if winner:
            embed.set_footer(text=f"🎉 Bravo à {winner.display_name} pour cette semaine !")
        
        await channel.send(embed=embed)
    
    @app_commands.command(name="rang", description="Voir ton niveau et tes statistiques")
    async def rang(self, interaction):
        user_id = str(interaction.user.id)
        
        if user_id not in self.data["users"]:
            await interaction.response.send_message(
                "Tu n'as pas encore d'activité enregistrée. Commence à discuter pour gagner de l'XP ! 📈",
                ephemeral=True
            )
            return
        
        user_data = self.data["users"][user_id]
        total_xp = user_data.get("xp", 0)
        weekly_xp = user_data.get("weekly_xp", 0)
        messages = user_data.get("messages", 0)
        
        level = calculate_level(total_xp)
        progress, _ = get_level_progress(total_xp)
        
        # Calculer position
        all_users = sorted(
            self.data["users"].items(),
            key=lambda x: x[1].get("xp", 0),
            reverse=True
        )
        position = next((i for i, (uid, _) in enumerate(all_users) if uid == user_id), 0) + 1
        
        # Barre de progression
        filled = int(progress / 10)
        bar = "█" * filled + "░" * (10 - filled)
        
        embed = Embed(
            title=f"📊 Profil de {interaction.user.display_name}",
            color=0x3498db
        )
        embed.add_field(name="Niveau", value=str(level), inline=True)
        embed.add_field(name="Position", value=f"#{position}", inline=True)
        embed.add_field(name="Messages", value=str(messages), inline=True)
        embed.add_field(name="XP Total", value=str(total_xp), inline=True)
        embed.add_field(name="XP Semaine", value=str(weekly_xp), inline=True)
        embed.add_field(name="Progression", value=f"{bar} {progress:.1f}%", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="classement", description="Voir le classement global")
    async def classement(self, interaction):
        # Trier par XP total
        sorted_users = sorted(
            self.data["users"].items(),
            key=lambda x: x[1].get("xp", 0),
            reverse=True
        )[:10]
        
        if not sorted_users:
            await interaction.response.send_message(
                "Aucun membre n'a encore d'activité enregistrée !",
                ephemeral=True
            )
            return
        
        embed = Embed(
            title="🏆 Classement Global",
            description="Top 10 des membres les plus actifs !",
            color=0x9b59b6,
            timestamp=self._get_paris_now()
        )
        
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        
        for i, (user_id, data) in enumerate(sorted_users):
            user = self.bot.get_user(int(user_id))
            if not user:
                continue
            
            total_xp = data.get("xp", 0)
            level = calculate_level(total_xp)
            messages = data.get("messages", 0)
            
            medal = medals[i] if i < 10 else f"{i+1}."
            embed.add_field(
                name=f"{medal} {user.display_name}",
                value=f"Niveau {level} • {total_xp} XP • {messages} messages",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(EngagementCog(bot))
