import logging
import re

import discord
from discord import app_commands
from discord.ext import commands

import config
import utils

log = logging.getLogger("rwp-bot.dyscyplina")

NO_MENTIONS = discord.AllowedMentions.none()

# rozpoznawanie decyzji na końcu linii: "... (Druk nr 69) - ZA", "... - WOLNA RĘKA (uwaga)"
DECISION_RE = re.compile(
    r"^(?P<body>.+?)\s+[-–—]\s+"
    r"(?P<dec>WSTRZYMUJ[ĘE] SIĘ|WSTRZYMUJ[ĘE]|WOLNA R[ĘE]KA|PRZECIW|ZA)\b"
    r"(?P<rest>.*)$",
    re.IGNORECASE,
)


def _canon(dec: str) -> str:
    d = dec.upper()
    if d.startswith("WSTRZYMUJ"):
        return "WSTRZYMUJĘ SIĘ"
    if d.startswith("WOLNA"):
        return "WOLNA RĘKA"
    return d  # ZA / PRZECIW


def format_item(line: str) -> str:
    line = line.strip()
    m = DECISION_RE.match(line)
    if not m:
        return line  # linia bez rozpoznanej decyzji idzie bez zmian
    label = _canon(m.group("dec"))
    emoji = config.DISCIPLINE_EMOJIS[label]
    rest = m.group("rest").rstrip()
    return f"{m.group('body').strip()} - {label} {emoji}{rest}"


def build_messages(title: str, lines: list[str]) -> list[str]:
    """Składa treść w wiadomości po max ~1900 znaków (limit Discorda to 2000)."""
    header = f"# {config.DISCIPLINE_HEADER_EMOJI}  | `BLOK GŁOSOWAŃ NA {title.strip().upper()}`"
    ping = f"||<@&{config.DISCIPLINE_PING_ROLE_ID}>||" if config.DISCIPLINE_PING_ROLE_ID else ""

    chunks: list[str] = []
    current = header
    for line in lines:
        item = format_item(line)[:1800]
        if len(current) + 2 + len(item) > 1900:
            chunks.append(current)
            current = item
        else:
            current += "\n\n" + item
    if ping:
        if len(current) + 2 + len(ping) > 2000:
            chunks.append(current)
            current = ping
        else:
            current += "\n\n" + ping
    chunks.append(current)
    return chunks


class DisciplineModal(discord.ui.Modal, title="Dyscyplina głosowań"):
    posiedzenie = discord.ui.TextInput(
        label="Które posiedzenie / dzień",
        placeholder="np. 6. posiedzenie Sejmu XII kadencji - dzień 2",
        max_length=150,
    )
    glosowania = discord.ui.TextInput(
        label="Głosowania (każde w osobnej linii)",
        style=discord.TextStyle.paragraph,
        placeholder="Projekt ustawy ... (Druk nr 69) - ZA   |   ... - WOLNA RĘKA (uwaga)",
        max_length=4000,
    )

    async def on_submit(self, interaction: discord.Interaction):
        lines = [l for l in self.glosowania.value.splitlines() if l.strip()]
        if not lines:
            await interaction.response.send_message("❌ Wpisz przynajmniej jedno głosowanie.", ephemeral=True)
            return

        channel = interaction.client.get_channel(config.DISCIPLINE_CHANNEL_ID)
        if channel is None:
            await interaction.response.send_message(
                f"❌ Nie widzę kanału {config.DISCIPLINE_CHANNEL_ID} (ustaw DISCIPLINE_CHANNEL_ID).",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        try:
            first = None
            for text in build_messages(self.posiedzenie.value, lines):
                msg = await channel.send(text, allowed_mentions=discord.AllowedMentions(roles=True))
                first = first or msg
        except discord.HTTPException as e:
            await interaction.followup.send(f"❌ Nie udało się wysłać dyscypliny: {e}", ephemeral=True)
            return

        await interaction.followup.send(f"✅ Dyscyplina opublikowana: {first.jump_url}", ephemeral=True)

        log_ch = interaction.client.get_channel(config.LOG_CHANNEL_ID)
        if log_ch:
            try:
                await log_ch.send(
                    f"⚖️ <@{interaction.user.id}> opublikował dyscyplinę głosowań ({len(lines)} pkt)\n{first.jump_url}",
                    allowed_mentions=NO_MENTIONS,
                )
            except discord.HTTPException:
                log.exception("Nie udało się wysłać loga")


class Dyscyplina(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="dyscyplina", description="Opublikuj dyscyplinę głosowań na posiedzenie")
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    @utils.can_use()
    async def dyscyplina(self, interaction: discord.Interaction):
        await interaction.response.send_modal(DisciplineModal())


async def setup(bot: commands.Bot):
    await bot.add_cog(Dyscyplina(bot))