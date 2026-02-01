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
        
        # Ignorer les DM (pas de guild donc pas d'emojis personnalisés)
        if not message.guild:
            return
        
        content_lower = message.content.lower()
        reactions_added = []
        
        # Debug: afficher les emojis disponibles (à retirer après test)
        # available_emojis = [e.name for e in message.guild.emojis]
        # print(f"Emojis disponibles: {available_emojis}")
        
        # Chercher :hap:
        if ":hap:" in content_lower:
            try:
                # Chercher l'emoji personnalisé "hap" dans le serveur
                hap_emoji = None
                for emoji in message.guild.emojis:
                    if emoji.name.lower() == "hap":
                        hap_emoji = emoji
                        break
                
                if hap_emoji:
                    await message.add_reaction(hap_emoji)
                    reactions_added.append("hap")
                    print(f"[Reactions] Emoji :hap: ajouté au message {message.id}")
            except Exception as e:
                print(f"[Reactions] Erreur lors de l'ajout de :hap: : {e}")
        
        # Chercher :noel:
        if ":noel:" in content_lower:
            try:
                # Chercher l'emoji personnalisé "noel" dans le serveur
                noel_emoji = None
                for emoji in message.guild.emojis:
                    if emoji.name.lower() == "noel":
                        noel_emoji = emoji
                        break
                
                if noel_emoji:
                    await message.add_reaction(noel_emoji)
                    reactions_added.append("noel")
                    print(f"[Reactions] Emoji :noel: ajouté au message {message.id}")
            except Exception as e:
                print(f"[Reactions] Erreur lors de l'ajout de :noel: : {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(ReactionsCog(bot))
