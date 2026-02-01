import re
from discord.ext import commands


class ReactionsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Mapping des emojis texte vers les vrais emojis Discord
        self.emoji_mapping = {
            ":hap:": "hap",
            ":noel:": "noel",
        }
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Détecte :hap: et :noel: dans les messages et réagit avec les emojis correspondants."""
        # Ignorer les messages du bot
        if message.author.bot:
            return
        
        content_lower = message.content.lower()
        reactions_added = []
        
        # Chercher :hap:
        if ":hap:" in content_lower:
            try:
                # Essayer de réagir avec l'emoji personnalisé
                hap_emoji = None
                for emoji in message.guild.emojis:
                    if emoji.name.lower() == "hap":
                        hap_emoji = emoji
                        break
                
                if hap_emoji:
                    await message.add_reaction(hap_emoji)
                    reactions_added.append("hap")
            except:
                pass  # Silencieux si l'emoji n'existe pas
        
        # Chercher :noel:
        if ":noel:" in content_lower:
            try:
                # Essayer de réagir avec l'emoji personnalisé
                noel_emoji = None
                for emoji in message.guild.emojis:
                    if emoji.name.lower() == "noel":
                        noel_emoji = emoji
                        break
                
                if noel_emoji:
                    await message.add_reaction(noel_emoji)
                    reactions_added.append("noel")
            except:
                pass  # Silencieux si l'emoji n'existe pas
        
        # Alternative: réagir avec des emojis unicode si les personnalisés ne sont pas trouvés
        if ":hap:" in content_lower and "hap" not in reactions_added:
            try:
                await message.add_reaction("😄")
            except:
                pass
        
        if ":noel:" in content_lower and "noel" not in reactions_added:
            try:
                await message.add_reaction("🎄")
            except:
                pass


async def setup(bot: commands.Bot):
    await bot.add_cog(ReactionsCog(bot))
