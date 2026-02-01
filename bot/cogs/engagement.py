import asyncio
import json
import logging
import os
import random
from datetime import datetime, timedelta
from io import BytesIO
from typing import TypedDict

import pytz
from discord import Embed, File
from discord.ext import commands, tasks
from PIL import Image, ImageDraw, ImageFont

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
        """Retourne les donnees analytics utiles pour la carte profil."""
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

    async def _build_profile_card(self, user, user_data: EngagementUser, analytics_data: dict) -> BytesIO:
        """Genere une carte profil PNG en memoire."""
        width, height = 720, 420
        image = Image.new("RGB", (width, height), (15, 18, 28))
        draw = ImageDraw.Draw(image)

        # Gradient simple
        for y in range(height):
            r = 15 + int(30 * (y / height))
            g = 18 + int(40 * (y / height))
            b = 28 + int(60 * (y / height))
            draw.line((0, y, width, y), fill=(r, g, b))

        # Panels
        draw.rounded_rectangle((24, 24, width - 24, height - 24), radius=24, fill=(20, 24, 38))
        draw.rounded_rectangle((32, 32, width - 32, 170), radius=20, fill=(24, 30, 48))
        draw.rounded_rectangle((32, 182, width - 32, height - 32), radius=20, fill=(24, 30, 48))

        # Avatar cercle
        avatar_bytes = await user.display_avatar.read()
        avatar = Image.open(BytesIO(avatar_bytes)).convert("RGBA").resize((110, 110))
        mask = Image.new("L", (110, 110), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse((0, 0, 110, 110), fill=255)
        image.paste(avatar, (52, 46), mask)

        # Fonts
        title_font = ImageFont.load_default()
        small_font = ImageFont.load_default()

        # Header text
        draw.text((180, 52), f"{user.display_name}", font=title_font, fill=(236, 242, 255))

        total_xp = user_data.get("xp", 0)
        weekly_xp = user_data.get("weekly_xp", 0)
        level = calculate_level(total_xp)
        progress, _ = get_level_progress(total_xp)

        draw.text((180, 80), f"Niveau {level}  |  XP {total_xp}", font=small_font, fill=(170, 180, 200))
        draw.text((180, 100), f"Semaine {weekly_xp} XP", font=small_font, fill=(140, 160, 190))

        # Progress bar
        bar_x, bar_y, bar_w, bar_h = 180, 125, 480, 12
        draw.rounded_rectangle((bar_x, bar_y, bar_x + bar_w, bar_y + bar_h), radius=6, fill=(38, 46, 68))
        fill_w = int(bar_w * (progress / 100))
        draw.rounded_rectangle((bar_x, bar_y, bar_x + max(fill_w, 6), bar_y + bar_h), radius=6, fill=(86, 210, 180))
        draw.text((bar_x + bar_w + 10, bar_y - 2), f"{progress:.1f}%", font=small_font, fill=(170, 180, 200))

        # Analytics blocks
        emoji_usage = analytics_data.get("emoji_usage", {})
        word_counts = analytics_data.get("word_counts", {})
        segments = analytics_data.get("segments", {})

        top_emojis = sorted(emoji_usage.items(), key=lambda item: (-item[1], item[0]))[:3]
        top_words = sorted(word_counts.items(), key=lambda item: (-item[1], item[0]))[:5]

        segment_labels = {
            "night": "Nuit",
            "morning": "Matin",
            "afternoon": "Apres-midi",
            "evening": "Soir",
        }
        dominant_label = "-"
        if segments:
            dominant_segment = max(segments.items(), key=lambda item: item[1])[0]
            dominant_label = segment_labels.get(dominant_segment, "-")

        left_x = 52
        right_x = 370
        top_y = 200

        draw.text((left_x, top_y), "Top emojis", font=small_font, fill=(200, 210, 230))
        emoji_text = " ".join([emoji for emoji, _ in top_emojis]) if top_emojis else "-"
        draw.text((left_x, top_y + 20), emoji_text, font=title_font, fill=(236, 242, 255))

        draw.text((left_x, top_y + 60), "Top mots", font=small_font, fill=(200, 210, 230))
        words_text = ", ".join([word for word, _ in top_words]) if top_words else "-"
        draw.text((left_x, top_y + 80), words_text, font=small_font, fill=(236, 242, 255))

        draw.text((right_x, top_y), "Tranche dominante", font=small_font, fill=(200, 210, 230))
        draw.text((right_x, top_y + 20), dominant_label, font=title_font, fill=(236, 242, 255))

        streak_days = user_data.get("streak_days", 0)
        draw.text((right_x, top_y + 60), "Streak", font=small_font, fill=(200, 210, 230))
        draw.text((right_x, top_y + 80), f"{streak_days} jours", font=title_font, fill=(236, 242, 255))

        output = BytesIO()
        image.save(output, format="PNG")
        output.seek(0)
        return output
    
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
        
        guild_id = message.guild.id
        user_id = message.author.id
        
        # Vérifier cooldown anti-spam
        if not self._check_cooldown(guild_id, user_id):
            return
        
        # Ajouter XP (5-15 aléatoire)
        xp_gain = random.randint(XP_PER_MESSAGE_MIN, XP_PER_MESSAGE_MAX)
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
        card = await self._build_profile_card(ctx.author, user_data, analytics_data)
        await ctx.send(file=File(fp=card, filename="profil.png"))
    
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
