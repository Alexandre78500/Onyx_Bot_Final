import logging

from discord import Intents, Object
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

from . import config


logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
)


class LucidBot(commands.Bot):
    def __init__(self):
        intents = Intents.default()
        intents.message_content = True  # Nécessaire pour lire les messages (GM)
        super().__init__(command_prefix=["o!", "O!"], intents=intents, help_command=None)

    async def setup_hook(self):
        await self.load_extension("bot.cogs.lucid")
        await self.load_extension("bot.cogs.gm")
        await self.load_extension("bot.cogs.engagement")
        await self.load_extension("bot.cogs.help")

        if config.GUILD_ID:
            guild = Object(id=config.GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()

    async def on_ready(self):
        logging.info("Logged in as %s (id=%s)", self.user, self.user.id)
        logging.info("Connected to %s guild(s)", len(self.guilds))


def main():
    if not config.DISCORD_TOKEN:
        raise RuntimeError("Missing DISCORD_TOKEN in environment")

    bot = LucidBot()
    bot.run(config.DISCORD_TOKEN)


if __name__ == "__main__":
    main()
