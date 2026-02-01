import discord
from discord.ext import commands


class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="help", aliases=["aide", "commands", "commandes"])
    async def help_command(self, ctx):
        """Affiche toutes les commandes disponibles"""
        
        embed = discord.Embed(
            title="📖 Commandes disponibles",
            description="Voici toutes les commandes que tu peux utiliser :",
            color=0x3498db
        )
        
        # Commandes Rêves Lucides
        embed.add_field(
            name="🌙 Rêves Lucides (Slash /)",
            value="""
            `/conseil` - Obtenir un conseil pour faire des rêves lucides
            `/journal` - Sauvegarder une note de rêve
            `/ressource` - Partager une ressource utile
            """,
            inline=False
        )
        
        # Commandes Engagement
        embed.add_field(
            name="📊 Engagement (Slash / et Préfixé !)",
            value="""
            `/rang` ou `!rang` - Voir ton niveau et tes statistiques
            `/classement` ou `!classement` - Voir le top 10 global
            """,
            inline=False
        )
        
        # Features automatiques
        embed.add_field(
            name="🤖 Features automatiques",
            value="""
            `gm` - Dis "gm" pour recevoir un message personnalisé (une fois/jour)
            **Classement hebdomadaire** - Posté automatiquement dimanche 20h
            **XP automatique** - Gagne de l'XP en discutant (cooldown 15s)
            """,
            inline=False
        )
        
        # Infos
        embed.add_field(
            name="ℹ️ Informations",
            value="""
            • Les commandes avec `/` sont des **slash commands**
            • Les commandes avec `!` sont des **commandes préfixées**
            • Les deux fonctionnent, utilise celle que tu préfères !
            """,
            inline=False
        )
        
        embed.set_footer(text=f"Bot {self.bot.user.name} • Demandé par {ctx.author.display_name}")
        
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCog(bot))
