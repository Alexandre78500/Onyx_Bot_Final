NOTIFY_DELETE_AFTER_SECONDS = 60
NOTIFY_CHANNEL_ID = 376797166334640128


async def notify_user_in_channel(ctx) -> bool:
    channel = ctx.guild.get_channel(NOTIFY_CHANNEL_ID) if ctx.guild else None
    if not channel:
        return False

    await channel.send(f"{ctx.author.mention} ici !", delete_after=NOTIFY_DELETE_AFTER_SECONDS)
    return True
