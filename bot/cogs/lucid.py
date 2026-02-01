import random

from discord import Interaction, app_commands
from discord.ext import commands


LUCID_TIPS = [
    "Keep a dream journal next to your bed.",
    "Do a reality check every time you see a mirror.",
    "Set a simple intention before sleep: notice you are dreaming.",
    "Wake up after 5 hours, stay up 10 minutes, then go back to sleep.",
    "Look for recurring dream signs and question them during the day.",
]


class LucidCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="tip", description="Get a lucid dreaming tip")
    async def tip(self, interaction: Interaction):
        tip = random.choice(LUCID_TIPS)
        await interaction.response.send_message(f"Tip: {tip}")

    @app_commands.command(name="journal", description="Save a dream note")
    @app_commands.describe(entry="Your dream entry")
    async def journal(self, interaction: Interaction, entry: str):
        await interaction.response.send_message(
            "Note saved (local only for now).", ephemeral=True
        )

    @app_commands.command(name="resource", description="Share a useful resource")
    async def resource(self, interaction: Interaction):
        await interaction.response.send_message(
            "Resource: https://en.wikipedia.org/wiki/Lucid_dream"
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(LucidCog(bot))
