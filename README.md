# Lucid Dreaming Discord Bot

Minimal discord.py slash-command bot focused on lucid dreaming.

## Setup
1) Create a virtual environment
2) Install dependencies:
   pip install -r requirements.txt
3) Copy `.env.example` to `.env` and fill in your token
4) Run:
   python -m bot.main

## Notes
- Set `GUILD_ID` for faster slash command sync during development.
- Remove `GUILD_ID` to sync globally (can take up to an hour).
