import asyncio
import json
import logging
import os
import random
import re
from datetime import datetime, timedelta
from typing import TypedDict

import pytz
from discord import Embed
from discord.ext import commands, tasks

from bot.constants import (
    ENGAGEMENT_COOLDOWN_SECONDS,
    ENGAGEMENT_SAVE_INTERVAL_SECONDS,
    XP_GM_BONUS as CONST_XP_GM_BONUS,
    XP_PER_MESSAGE_MAX as CONST_XP_PER_MESSAGE_MAX,
    XP_PER_MESSAGE_MIN as CONST_XP_PER_MESSAGE_MIN,
)

# Configuration
PARIS_TZ = pytz.timezone('Europe/Paris')
DATA_FILE = "engagement_data.json"
COOLDOWN_SECONDS = ENGAGEMENT_COOLDOWN_SECONDS  # Anti-spam: 15 secondes entre chaque comptabilisation
SAVE_INTERVAL_SECONDS = ENGAGEMENT_SAVE_INTERVAL_SECONDS  # Sauvegarde toutes les 60s max

# Gains d'XP
XP_PER_MESSAGE_MIN = CONST_XP_PER_MESSAGE_MIN
XP_PER_MESSAGE_MAX = CONST_XP_PER_MESSAGE_MAX
XP_GM_BONUS = CONST_XP_GM_BONUS

logger = logging.getLogger(__name__)

URL_RE = re.compile(r"https?://\S+")
CUSTOM_EMOJI_RE = re.compile(r"<a?:([A-Za-z0-9_]+):\d+>")
SHORTCODE_EMOJI_RE = re.compile(r":([A-Za-z0-9_]+):")
UNICODE_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001F5FF"
    "\U0001F600-\U0001F64F"
    "\U0001F680-\U0001F6FF"
    "\U0001F700-\U0001F77F"
    "\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "\U00002700-\U000027BF"
    "\U00002600-\U000026FF"
    "]",
    re.UNICODE,
)


class EngagementUser(TypedDict):
    xp: int
    weekly_xp: int
    messages: int
    last_active: str | None
    display_name: str | None
    streak_days: int
    last_streak_date: str | None


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
        self.data = {"guilds": {}}  # Structure: {guild_id: {users: {}, weekly_reset: None, channel_id: None}}
        self.cooldowns = {}  # {(guild_id, user_id): last_message_time}
        self._dirty = False  # Flag: True si données modifiées depuis dernière sauvegarde
        self._load_data()
        self.periodic_save.start()  # Sauvegarde périodique
        self.weekly_ranking.start()
    
    def cog_unload(self):
        self.periodic_save.cancel()
        self.weekly_ranking.cancel()
        # Sauvegarder à la fermeture
        if self._dirty:
            self._save_data_sync()
    
    def _get_guild_data(self, guild_id: int):
        """Récupère ou crée les données d'un serveur."""
        guild_id_str = str(guild_id)
        if guild_id_str not in self.data["guilds"]:
            guild_data = {
                "users": {},
                "weekly_reset": None,
                "channel_id": None
            }
            self.data["guilds"][guild_id_str] = guild_data
            # Initialiser le prochain reset
            self._set_next_weekly_reset(guild_id, guild_data)
            self._dirty = True
        return self.data["guilds"][guild_id_str]
    
    def _set_next_weekly_reset(self, guild_id: int, guild_data: dict | None = None):
        """Définit le prochain reset hebdomadaire (dimanche 20h) pour un serveur."""
        now = self._get_paris_now()
        # Trouver le prochain dimanche
        days_until_sunday = (6 - now.weekday()) % 7
        if days_until_sunday == 0 and now.hour >= 20:
            # Si c'est déjà dimanche après 20h, prendre dimanche prochain
            days_until_sunday = 7
        next_reset = now + timedelta(days=days_until_sunday)
        next_reset = next_reset.replace(hour=20, minute=0, second=0, microsecond=0)
        
        if guild_data is None:
            guild_data = self._get_guild_data(guild_id)
        if guild_data is None:
            return
        guild_data["weekly_reset"] = next_reset
        self._dirty = True
    
    def _load_data(self):
        """Charge les données depuis le fichier JSON."""
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, 'r', encoding='utf-8') as f:
                    loaded_data = json.load(f)
                    # Migration des anciennes données (global -> guilds)
                    if "users" in loaded_data and "guilds" not in loaded_data:
                        logger.info("Migration des données d'engagement vers le nouveau format...")
                        self.data = {"guilds": {}}
                        # On met les anciennes données dans un guild "legacy" (sera ignoré)
                    else:
                        self.data = loaded_data
                        # Convertir les dates pour chaque guild
                        for guild_data in self.data.get("guilds", {}).values():
                            if guild_data.get("weekly_reset"):
                                guild_data["weekly_reset"] = datetime.fromisoformat(guild_data["weekly_reset"])
            except Exception as e:
                logger.error(f"Erreur chargement engagement: {e}")
                self.data = {"guilds": {}}
    
    def _save_data_sync(self):
        """Sauvegarde synchrone des données (utilisée au shutdown)."""
        try:
            data_to_save = {"guilds": {}}
            for guild_id, guild_data in self.data["guilds"].items():
                data_to_save["guilds"][guild_id] = {
                    "users": guild_data["users"],
                    "weekly_reset": guild_data["weekly_reset"].isoformat() if guild_data.get("weekly_reset") else None,
                    "channel_id": guild_data.get("channel_id")
                }
            
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, ensure_ascii=False, indent=2)
            
            self._dirty = False
            logger.info("[Engagement] Données sauvegardées")
        except Exception as e:
            logger.error(f"[Engagement] Erreur sauvegarde: {e}")
    
    async def _save_data_async(self):
        """Sauvegarde asynchrone via executor."""
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._save_data_sync)
        except Exception as e:
            logger.error(f"[Engagement] Erreur sauvegarde async: {e}")
    
    @tasks.loop(seconds=SAVE_INTERVAL_SECONDS)
    async def periodic_save(self):
        """Sauvegarde périodique si données modifiées."""
        if self._dirty:
            await self._save_data_async()
    
    @periodic_save.before_loop
    async def before_periodic_save(self):
        await self.bot.wait_until_ready()
    
    def _get_paris_now(self):
        """Retourne la datetime actuelle à Paris."""
        return datetime.now(PARIS_TZ)

    def _extract_countable_words(self, text: str) -> list[str]:
        if not text:
            return []

        text = text.lower()
        text = URL_RE.sub(" ", text)
        text = CUSTOM_EMOJI_RE.sub(" ", text)
        text = SHORTCODE_EMOJI_RE.sub(" ", text)
        text = UNICODE_EMOJI_RE.sub(" ", text)

        for char in ".,;:!?\"'()[]{}@#&-_=+/*$%":
            text = text.replace(char, " ")

        return [w.strip() for w in text.split() if w.strip()]
    
    def _check_cooldown(self, guild_id: int, user_id: int) -> bool:
        """Vérifie si l'utilisateur peut gagner de l'XP (cooldown 15s)."""
        now = self._get_paris_now()
        cooldown_key = (guild_id, user_id)
        if cooldown_key in self.cooldowns:
            last_time = self.cooldowns[cooldown_key]
            if (now - last_time).total_seconds() < COOLDOWN_SECONDS:
                return False
        self.cooldowns[cooldown_key] = now
        return True
    
    def _add_xp(self, guild_id: int, user_id: int, xp_amount: int, user_name: str | None = None, is_weekly: bool = True) -> tuple[EngagementUser, int, int]:
        """Ajoute de l'XP à un utilisateur dans un serveur spécifique."""
        guild_data = self._get_guild_data(guild_id)
        user_id_str = str(user_id)
        
        if user_id_str not in guild_data["users"]:
            guild_data["users"][user_id_str] = {
                "xp": 0,
                "weekly_xp": 0,
                "messages": 0,
                "last_active": None,
                "display_name": user_name,
                "streak_days": 0,
                "last_streak_date": None
            }
        
        user_data: EngagementUser = guild_data["users"][user_id_str]
        
        # Calculer le niveau avant l'ajout d'XP
        old_level = calculate_level(user_data["xp"])
        
        user_data["xp"] += xp_amount
        if is_weekly:
            user_data["weekly_xp"] += xp_amount
        user_data["messages"] += 1
        user_data["last_active"] = self._get_paris_now().isoformat()
        if user_name:
            user_data["display_name"] = user_name
        
        # Mettre à jour le streak
        self._update_streak(user_data)
        
        # Vérifier si niveau up
        new_level = calculate_level(user_data["xp"])
        
        # Marquer comme modifié (sera sauvegardé périodiquement)
        self._dirty = True
        
        return user_data, old_level, new_level

    def _get_analytics_snapshot(self, guild_id: int, user_id: int) -> dict:
        """Retourne les donnees analytics utiles pour l'embed profil."""
        analytics = self.bot.get_cog("AnalyticsCog")
        if not analytics:
            return {}

        try:
            guild_data = analytics._get_guild_data(str(guild_id))
        except Exception:
            return {}

        stats = guild_data.get("global_stats", {})
        user_id_str = str(user_id)

        emoji_usage = stats.get("emoji_text_usage", {}).get("users", {}).get(user_id_str, {})
        word_counts = stats.get("word_counts", {})
        segments = stats.get("messages_by_segment", {})

        return {
            "emoji_usage": emoji_usage,
            "word_counts": word_counts,
            "segments": segments,
        }

    def _build_profile_embed(self, user, user_data: EngagementUser, analytics_data: dict, position: int) -> Embed:
        """Genere un embed profil sobre et riche."""
        total_xp = user_data.get("xp", 0)
        weekly_xp = user_data.get("weekly_xp", 0)
        messages = user_data.get("messages", 0)
        level = calculate_level(total_xp)
        progress, _ = get_level_progress(total_xp)
        streak_days = user_data.get("streak_days", 0)

        # Analytics
        emoji_usage = analytics_data.get("emoji_usage", {})
        word_counts = analytics_data.get("word_counts", {})
        segments = analytics_data.get("segments", {})

        top_emojis = sorted(emoji_usage.items(), key=lambda item: (-item[1], item[0]))[:3]
        top_words = sorted(word_counts.items(), key=lambda item: (-item[1], item[0]))[:5]

        segment_labels = {"night": "Nuit 🌙", "morning": "Matin ☀️", "afternoon": "Après-midi 🌤️", "evening": "Soir 🌆"}
        dominant_segment = ""
        if segments:
            dominant_key = max(segments.items(), key=lambda x: x[1])[0]
            dominant_segment = segment_labels.get(dominant_key, "N/A")

        # Barre de progression
        filled = int(progress / 10)
        bar = "▰" * filled + "▱" * (10 - filled)

        embed = Embed(
            title=f"📊 Profil de {user.display_name}",
            description="Statistiques personnelles",
            color=0x5865F2
        )
        embed.set_thumbnail(url=user.display_avatar.url)

        # Niveau + XP
        embed.add_field(
            name="📈 Niveau & Progression",
            value=f"**Niveau {level}**\n{bar} `{progress:.1f}%`",
            inline=False
        )

        # XP
        embed.add_field(
            name="✨ Expérience",
            value=f"**Total :** {total_xp:,} XP\n**Semaine :** {weekly_xp:,} XP",
            inline=True
        )

        # Position + Messages
        embed.add_field(
            name="🏆 Classement",
            value=f"**Position :** #{position}\n**Messages :** {messages:,}",
            inline=True
        )

        # Streak
        if streak_days > 0:
            streak_icon = "🔥" if streak_days >= 7 else "⚡"
            embed.add_field(
                name=f"{streak_icon} Streak",
                value=f"**{streak_days}** jour{'s' if streak_days > 1 else ''}",
                inline=True
            )

        # Top emojis
        if top_emojis:
            emojis_text = " ".join([f"{emoji} ({count})" for emoji, count in top_emojis])
            embed.add_field(
                name="😄 Top Emojis",
                value=emojis_text,
                inline=False
            )

        # Top mots
        if top_words:
            words_text = ", ".join([f"`{word}`" for word, _ in top_words])
            embed.add_field(
                name="💬 Mots Favoris",
                value=words_text,
                inline=False
            )

        # Tranche dominante
        if dominant_segment:
            embed.add_field(
                name="🕐 Période d'Activité",
                value=dominant_segment,
                inline=False
            )

        embed.set_footer(text="Statistiques mises à jour en temps réel")
        return embed
    
    def _update_streak(self, user_data: EngagementUser):
        """Met à jour le streak journalier de l'utilisateur."""
        now = self._get_paris_now()
        today = now.date()
        
        last_streak_str = user_data.get("last_streak_date")
        if last_streak_str:
            last_streak = datetime.fromisoformat(last_streak_str).date()
            
            # Si c'était hier, on incrémente
            if last_streak == today - timedelta(days=1):
                user_data["streak_days"] = user_data.get("streak_days", 0) + 1
                user_data["last_streak_date"] = now.isoformat()
                self._dirty = True
            # Si c'était aujourd'hui, on ne fait rien (déjà compté)
            elif last_streak == today:
                pass
            # Sinon (plus de 1 jour d'écart), on reset
            else:
                user_data["streak_days"] = 1
                user_data["last_streak_date"] = now.isoformat()
                self._dirty = True
        else:
            # Premier jour
            user_data["streak_days"] = 1
            user_data["last_streak_date"] = now.isoformat()
            self._dirty = True
    
    def _reset_weekly(self, guild_id: int):
        """Reset les stats hebdomadaires pour un serveur."""
        guild_data = self._get_guild_data(guild_id)
        for user_data in guild_data["users"].values():
            user_data["weekly_xp"] = 0
        
        self._set_next_weekly_reset(guild_id, guild_data)
        self._dirty = True
    
    @commands.Cog.listener()
    async def on_message(self, message):
        # Ignorer bot et DM
        if message.author.bot or not message.guild:
            return

        if not self._extract_countable_words(message.content):
            return
        
        guild_id = message.guild.id
        user_id = message.author.id
        
        # Vérifier cooldown anti-spam
        if not self._check_cooldown(guild_id, user_id):
            return
        
        # Ajouter XP (5-15 aléatoire)
        xp_gain = XP_PER_MESSAGE_MIN
        user_data, old_level, new_level = self._add_xp(guild_id, user_id, xp_gain, message.author.display_name)
        
        # Si level up, envoyer un message de félicitations
        if new_level > old_level:
            await self._send_level_up_message(message.channel, message.author, new_level)
    
    @tasks.loop(minutes=1)
    async def weekly_ranking(self):
        """Poste le classement hebdomadaire pour chaque serveur le dimanche à 20h."""
        now = self._get_paris_now()
        
        for guild_id_str, guild_data in self.data.get("guilds", {}).items():
            weekly_reset = guild_data.get("weekly_reset")
            if weekly_reset and now >= weekly_reset:
                await self._post_ranking(int(guild_id_str))
                self._reset_weekly(int(guild_id_str))
                # Forcer sauvegarde après reset
                if self._dirty:
                    await self._save_data_async()
    
    @weekly_ranking.before_loop
    async def before_weekly_ranking(self):
        await self.bot.wait_until_ready()
    
    async def _send_level_up_message(self, channel, user, new_level: int):
        """Envoie un message de félicitations pour un level up."""
        messages = [
            f"🎉 Félicitations {user.mention} ! Tu passes au **Niveau {new_level}** ! Continue comme ça !",
            f"🚀 Wouah {user.mention} ! Niveau {new_level} atteint ! Tu progresses vite !",
            f"⭐ Bravo {user.mention} ! Tu es maintenant au **Niveau {new_level}** !",
            f"🎯 Incroyable {user.mention} ! Passage au Niveau {new_level} ! 🎊",
            f"💪 Excellent {user.mention} ! Niveau {new_level} débloqué !",
        ]
        
        # Messages spéciaux pour certains niveaux
        if new_level == 5:
            msg = f"🎉 {user.mention} atteint le **Niveau 5** ! Tu deviens un vrai habitué ! 🌟"
        elif new_level == 10:
            msg = f"🏆 {user.mention} passe au **Niveau 10** ! Tu es un membre d'exception ! ✨"
        elif new_level == 25:
            msg = f"👑 {user.mention} atteint le **Niveau 25** ! Légendaire ! 🔥"
        elif new_level == 50:
            msg = f"🌟 {user.mention} débloque le **Niveau 50** ! Tu es une légende vivante ! 👑"
        elif new_level % 10 == 0:
            msg = f"🎊 {user.mention} passe au **Niveau {new_level}** ! Un nouveau palier atteint ! 🚀"
        else:
            msg = random.choice(messages)
        
        try:
            await channel.send(msg)
        except:
            pass  # Silencieux si erreur
    
    async def _get_display_name(self, guild, user_id: int, user_data: dict) -> str:
        """Récupère le nom d'affichage d'un utilisateur avec fallback."""
        # Essayer de récupérer depuis le cache Discord
        if guild:
            member = guild.get_member(user_id)
            if member:
                # Mettre à jour le nom stocké
                user_data["display_name"] = member.display_name
                self._dirty = True
                return member.display_name
        
        # Fallback sur le nom stocké
        stored_name = user_data.get("display_name")
        if stored_name:
            return stored_name
        
        # Dernier recours: essayer de fetch l'utilisateur
        try:
            user = await self.bot.fetch_user(user_id)
            if user:
                user_data["display_name"] = user.display_name
                self._dirty = True
                return user.display_name
        except:
            pass
        
        return f"Utilisateur {user_id}"
    
    async def _post_ranking(self, guild_id: int):
        """Poste le classement dans le canal configuré du serveur."""
        guild_data = self._get_guild_data(guild_id)
        channel_id = guild_data.get("channel_id")
        
        if not channel_id:
            # Pas de canal configuré, essayer de trouver un canal général
            guild = self.bot.get_guild(guild_id)
            if not guild:
                return
            # Chercher un canal nommé "général" ou "general"
            for channel in guild.text_channels:
                if "général" in channel.name.lower() or "general" in channel.name.lower():
                    channel_id = channel.id
                    guild_data["channel_id"] = channel_id
                    self._dirty = True
                    break
            if not channel_id:
                return
        
        channel = self.bot.get_channel(channel_id)
        if not channel:
            return
        
        # Trier par XP hebdomadaire
        sorted_users = sorted(
            guild_data["users"].items(),
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
        guild = self.bot.get_guild(guild_id)
        
        for i, (user_id, data) in enumerate(sorted_users):
            display_name = await self._get_display_name(guild, int(user_id), data)
            
            weekly_xp = data.get("weekly_xp", 0)
            total_xp = data.get("xp", 0)
            level = calculate_level(total_xp)
            
            medal = medals[i] if i < 10 else f"{i+1}."
            embed.add_field(
                name=f"{medal} {display_name}",
                value=f"Niveau {level} • {weekly_xp} XP cette semaine",
                inline=False
            )
        
        # Mention du gagnant
        winner_id = sorted_users[0][0]
        winner_data = sorted_users[0][1]
        winner_name = await self._get_display_name(guild, int(winner_id), winner_data)
        embed.set_footer(text=f"🎉 Bravo à {winner_name} pour cette semaine !")
        
        await channel.send(embed=embed)
    
    # Commandes préfixées uniquement (slash désactivé pour l'instant)
    @commands.command(name="profil", aliases=["rang", "rank", "stats", "niveau"])
    async def profil_prefix(self, ctx):
        """Carte profil (préfixé)"""
        if not ctx.guild:
            await ctx.send("Cette commande ne fonctionne pas en DM.")
            return
        
        guild_id = ctx.guild.id
        guild_data = self._get_guild_data(guild_id)
        user_id = str(ctx.author.id)
        
        if user_id not in guild_data["users"]:
            await ctx.send("Tu n'as pas encore d'activité enregistrée. Commence à discuter pour gagner de l'XP ! 📈")
            return
        
        user_data = guild_data["users"][user_id]
        analytics_data = self._get_analytics_snapshot(guild_id, int(user_id))
        
        # Calculer position
        all_users = sorted(
            guild_data["users"].items(),
            key=lambda x: x[1].get("xp", 0),
            reverse=True
        )
        position = next((i for i, (uid, _) in enumerate(all_users) if uid == user_id), 0) + 1
        
        embed = self._build_profile_embed(ctx.author, user_data, analytics_data, position)
        await ctx.send(embed=embed)
    
    @commands.command(name="classement", aliases=["ranking", "top", "leaderboard", "top10"])
    async def classement_prefix(self, ctx):
        """Voir le classement global (préfixé)"""
        if not ctx.guild:
            await ctx.send("Cette commande ne fonctionne pas en DM.")
            return
        
        guild_id = ctx.guild.id
        guild_data = self._get_guild_data(guild_id)
        
        # Trier par XP total
        sorted_users = sorted(
            guild_data["users"].items(),
            key=lambda x: x[1].get("xp", 0),
            reverse=True
        )[:10]
        
        if not sorted_users:
            await ctx.send("Aucun membre n'a encore d'activité enregistrée !")
            return
        
        embed = Embed(
            title="🏆 Classement Global",
            description="Top 10 des membres les plus actifs !",
            color=0x9b59b6,
            timestamp=self._get_paris_now()
        )
        
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        
        for i, (user_id, data) in enumerate(sorted_users):
            display_name = await self._get_display_name(ctx.guild, int(user_id), data)
            
            total_xp = data.get("xp", 0)
            level = calculate_level(total_xp)
            messages = data.get("messages", 0)
            
            medal = medals[i] if i < 10 else f"{i+1}."
            embed.add_field(
                name=f"{medal} {display_name}",
                value=f"Niveau {level} • {total_xp} XP • {messages} messages",
                inline=False
            )
        
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(EngagementCog(bot))
