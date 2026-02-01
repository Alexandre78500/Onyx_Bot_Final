from difflib import get_close_matches

from discord.ext import commands


class ErrorHandlerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _get_available_commands(self) -> list[str]:
        """Récupère les commandes et aliases enregistrés."""
        names: set[str] = set()
        for command in self.bot.commands:
            names.add(command.name)
            for alias in command.aliases:
                names.add(alias)
        return sorted(names)
    
    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """Gestionnaire d'erreurs global pour suggérer des commandes proches."""
        
        # Ignorer si c'est une commande inexistante
        if isinstance(error, commands.CommandNotFound):
            # Récupérer le message sans le préfixe
            content = ctx.message.content
            prefix = ctx.prefix if ctx.prefix else "o!"
            attempted_cmd = content[len(prefix):].split()[0] if content.startswith(prefix) else content.split()[0]
            
            # Chercher la commande la plus proche
            available_commands = self._get_available_commands()
            matches = get_close_matches(attempted_cmd.lower(), available_commands, n=1, cutoff=0.6)
            
            if matches:
                suggested_cmd = matches[0]
                await ctx.send(f"❓ Commande non trouvée. Tu voulais dire `o!{suggested_cmd}` ?")
            return
        
        # Pour les autres erreurs, on peut les logger ou les gérer différemment
        # Par défaut, on ne fait rien pour laisser l'erreur apparaître en console


async def setup(bot: commands.Bot):
    await bot.add_cog(ErrorHandlerCog(bot))
