from datetime import date, datetime

import discord
from discord import app_commands

import config


def can_use():
    """Komenda dla użytkownika o ID COMMAND_ROLE_ID albo osoby z rangą o tym ID."""

    async def predicate(interaction: discord.Interaction) -> bool:
        user = interaction.user
        if user.id == config.COMMAND_ROLE_ID:
            return True
        if isinstance(user, discord.Member) and any(r.id == config.COMMAND_ROLE_ID for r in user.roles):
            return True
        raise app_commands.CheckFailure("🚫 Nie masz uprawnień do tej komendy.")

    return app_commands.check(predicate)


def parse_date(text: str) -> date:
    t = text.strip().replace("/", ".").replace("-", ".").replace(" ", "")
    for fmt in ("%d.%m.%Y", "%d.%m.%y"):
        try:
            return datetime.strptime(t, fmt).date()
        except ValueError:
            continue
    raise ValueError("Zły format daty. Użyj DD.MM.RRRR, np. 12.11.2026")


def parse_dt(date_text: str, time_text: str) -> datetime:
    d = parse_date(date_text)
    t = time_text.strip().replace(".", ":").replace(" ", "")
    try:
        tm = datetime.strptime(t, "%H:%M").time()
    except ValueError:
        raise ValueError("Zły format godziny. Użyj GG:MM, np. 19:30")
    return datetime.combine(d, tm, tzinfo=config.TZ)


def mentions(ids: list, limit: int = 1000) -> str:
    out, length = [], 0
    for i, uid in enumerate(ids):
        m = f"<@{uid}>"
        if length + len(m) + 1 > limit:
            out.append(f"…i {len(ids) - i} więcej")
            break
        out.append(m)
        length += len(m) + 1
    return " ".join(out)


async def try_dm(user, **kwargs) -> bool:
    try:
        await user.send(**kwargs)
        return True
    except (discord.Forbidden, discord.HTTPException):
        return False
