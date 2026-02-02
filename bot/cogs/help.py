import discord
from discord.ext import commands

from bot.command_limits import notify_user_in_channel
from bot.constants import COMMAND_CHANNEL_IDS_GENERAL_ONLY

async def _ensure_allowed_channel(ctx, allowed_channel_ids: set[int]) -> bool:
    if not ctx.guild:
        await ctx.send("Cette commande ne fonctionne pas en DM.")
        return False

    if ctx.channel.id not in allowed_channel_ids:
        try:
            await ctx.message.delete()
        except Exception:
            pass
        await notify_user_in_channel(ctx)
        return False

    return True


class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="help", aliases=["aide", "commands", "commandes", "cmd"])
    async def help_command(self, ctx):
        """Affiche toutes les commandes disponibles"""
        if not await _ensure_allowed_channel(ctx, COMMAND_CHANNEL_IDS_GENERAL_ONLY):
            return
        
        embed = discord.Embed(
            title="🌙 Commandes Disponibles",
            description="Préfixe : `o!` ou `O!`",
            color=0x9b59b6
        )
        
        # Commandes principales
        embed.add_field(
            name="📋 Commandes Principales",
            value="""
            `o!help` - Affiche cette aide
            `o!conseil` - Conseil pour les rêves lucides
            `o!ressource` - Ressources sur les rêves lucides
            """,
            inline=False
        )
        
        # Commandes Engagement
        embed.add_field(
            name="📊 Système d'Engagement",
            value="""
            `o!rang` - Voir ton niveau et stats
            `o!classement` - Top 10 du serveur
            """,
            inline=False
        )
        
        # Features automatiques
        embed.add_field(
            name="✨ Features Automatiques",
            value="""
            Dis `gm` → Réponse personnalisée (1x/jour)
            Parle → Gagne de l'XP et monte en niveau !
            Niveau up → Félicitations automatiques 🎉
            `:hap:` ou `:noel:` → Réaction auto du bot
            Dimanche 20h → Classement hebdomadaire
            """,
            inline=False
        )
        
        # Tips
        embed.add_field(
            name="💡 Astuce",
            value="Si tu fais une faute de frappe (ex: `o!classsement`), le bot te suggère la bonne commande !",
            inline=False
        )
        
        embed.set_footer(text=f"{self.bot.user.name} • Tape o!help pour revoir les commandes")
        
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCog(bot))
