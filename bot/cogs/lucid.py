import random

from discord import Interaction, app_commands
from discord.ext import commands

from bot.constants import COMMAND_CHANNEL_IDS_LUCID

CONSEILS_REVE_LUCIDE = [
    "Garde un journal de rêves à côté de ton lit.",
    "Fais un test de réalité à chaque fois que tu vois un miroir.",
    "Fixe une intention simple avant de dormir : remarquer que tu rêves.",
    "Réveille-toi après 5 heures, reste debout 10 minutes, puis rendors-toi.",
    "Cherche des signes de rêves récurrents et questionne-les pendant la journée.",
]


def _format_channel_mentions(channel_ids: set[int]) -> str:
    return ", ".join(f"<#{channel_id}>" for channel_id in sorted(channel_ids))


async def _ensure_allowed_channel(ctx, allowed_channel_ids: set[int]) -> bool:
    if not ctx.guild:
        await ctx.send("Cette commande ne fonctionne pas en DM.")
        return False

    if ctx.channel.id not in allowed_channel_ids:
        channels_text = _format_channel_mentions(allowed_channel_ids)
        await ctx.send(
            f"Merci d'utiliser cette commande dans l'un de ces salons : {channels_text}."
        )
        return False

    return True


class LucidCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="conseil", aliases=["tip", "astuce"])
    async def conseil_prefix(self, ctx):
        """Obtenir un conseil pour faire des rêves lucides"""
        if not await _ensure_allowed_channel(ctx, COMMAND_CHANNEL_IDS_LUCID):
            return
        conseil = random.choice(CONSEILS_REVE_LUCIDE)
        await ctx.send(f"💡 **Conseil rêve lucide :** {conseil}")

    @commands.command(name="ressource", aliases=["lien", "resources"])
    async def ressource_prefix(self, ctx):
        """Partager une ressource utile sur les rêves lucides"""
        if not await _ensure_allowed_channel(ctx, COMMAND_CHANNEL_IDS_LUCID):
            return
        await ctx.send("📚 **Ressources rêves lucides :** https://fr.wikipedia.org/wiki/Rêve_lucide")

    # Slash commands désactivés pour l'instant
    # @app_commands.command(name="conseil", description="Obtenir un conseil pour faire des rêves lucides")
    # async def conseil(self, interaction: Interaction):
    #     conseil = random.choice(CONSEILS_REVE_LUCIDE)
    #     await interaction.response.send_message(f"💡 Conseil : {conseil}")
    #
    # @app_commands.command(name="journal", description="Sauvegarder une note de rêve")
    # @app_commands.describe(entree="Ton entrée de rêve")
    # async def journal(self, interaction: Interaction, entree: str):
    #     await interaction.response.send_message(
    #         "📝 Note sauvegardée (localement pour l'instant).", ephemeral=True
    #     )
    #
    # @app_commands.command(name="ressource", description="Partager une ressource utile")
    # async def ressource(self, interaction: Interaction):
    #     await interaction.response.send_message(
    #         "📚 Ressource : https://fr.wikipedia.org/wiki/Rêve_lucide"
    #     )


async def setup(bot: commands.Bot):
    await bot.add_cog(LucidCog(bot))
