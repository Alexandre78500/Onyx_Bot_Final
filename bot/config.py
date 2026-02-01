import os


def _get_env(name, default=""):
    return os.getenv(name, default).strip()


DISCORD_TOKEN = _get_env("DISCORD_TOKEN")
GUILD_ID = _get_env("GUILD_ID")

if GUILD_ID:
    try:
        GUILD_ID = int(GUILD_ID)
    except ValueError as exc:
        raise ValueError("GUILD_ID must be an integer") from exc
