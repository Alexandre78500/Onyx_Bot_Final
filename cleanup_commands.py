"""
Script pour supprimer les commandes slash en double d'un serveur spécifique.
À exécuter une seule fois sur le VPS.
"""
import asyncio
import os
from discord import Object
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = 376777553945296896  # Ton gros serveur


class CleanupBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!")

    async def setup_hook(self):
        guild = Object(id=GUILD_ID)
        
        # Récupère toutes les commandes guild-specific
        commands = await self.tree.fetch_commands(guild=guild)
        
        print(f"Commandes trouvées sur le serveur {GUILD_ID}:")
        for cmd in commands:
            print(f"  - {cmd.name} (ID: {cmd.id})")
        
        # Supprime toutes les commandes guild-specific
        self.tree.clear_commands(guild=guild)
        await self.tree.sync(guild=guild)
        
        print(f"\n✅ Commandes guild-specific supprimées du serveur {GUILD_ID}")
        print("Les commandes globales restent disponibles.")
        
        await self.close()


if __name__ == "__main__":
    if not TOKEN:
        print("❌ Erreur: DISCORD_TOKEN non trouvé dans .env")
        exit(1)
    
    bot = CleanupBot()
    bot.run(TOKEN)
