from time import monotonic


NOTIFY_COOLDOWN_SECONDS = 300
NOTIFY_DELETE_AFTER_SECONDS = 60
NOTIFY_CHANNEL_ID = 376797166334640128

_last_notify_by_user: dict[int, float] = {}


def _should_notify(user_id: int) -> bool:
    now = monotonic()
    last_notify = _last_notify_by_user.get(user_id)
    if last_notify is not None and (now - last_notify) < NOTIFY_COOLDOWN_SECONDS:
        return False
    _last_notify_by_user[user_id] = now
    return True


async def notify_user_in_channel(ctx) -> bool:
    if not _should_notify(ctx.author.id):
        return False

    channel = ctx.bot.get_channel(NOTIFY_CHANNEL_ID)
    if not channel:
        return False

    await channel.send(f"{ctx.author.mention} ici !", delete_after=NOTIFY_DELETE_AFTER_SECONDS)
    return True
