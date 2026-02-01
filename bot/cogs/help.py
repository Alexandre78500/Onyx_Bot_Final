import discord
from discord.ext import commands


class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="help", aliases=["aide", "commands", "commandes", "cmd"])
    async def help_command(self, ctx):
        """Affiche toutes les commandes disponibles"""
        
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
