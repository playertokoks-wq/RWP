import asyncio
import logging
import re
import time
import uuid
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

import config
import utils
from storage import Store

log = logging.getLogger("rwp-bot.posiedzenie")
store = Store("sessions")
lock = asyncio.Lock()

# Przypomnienia: godzinę i 15 minut przed startem
REMINDER_OFFSETS = (3600, 900)

STATUS_ORDER = ("yes", "maybe", "late", "no")
STATUS_LABELS = {
    "yes": "✅ Będę",
    "maybe": "❔ Nie wiem",
    "late": "🕒 Spóźnię się",
    "no": "❌ Nie będę",
}
BUTTON_LABELS = {"yes": "Będę", "maybe": "Nie wiem", "late": "Spóźnię się", "no": "Nie będę"}
BUTTON_STYLES = {
    "yes": discord.ButtonStyle.success,
    "maybe": discord.ButtonStyle.secondary,
    "late": discord.ButtonStyle.primary,
    "no": discord.ButtonStyle.danger,
}
NO_MENTIONS = discord.AllowedMentions.none()


# ---------- wygląd ----------
def locked_text(status: str) -> str:
    return f"🔒 Już odpowiedziałeś ({STATUS_LABELS[status]}). Odpowiedzi nie można zmienić."


def build_embed(s: dict) -> discord.Embed:
    ts = int(s["start_ts"])
    embed = discord.Embed(
        title=f"🏛️ Posiedzenie: {s['title']}",
        description=s.get("desc") or None,
        color=0x9B59B6,
    )
    embed.set_author(name=config.PARTY_NAME)
    embed.add_field(name="Termin", value=f"<t:{ts}:F> (<t:{ts}:R>)", inline=False)
    embed.add_field(name="📅 Wydarzenie", value=s["event_url"], inline=False)
    embed.add_field(name="📍 Podium (gdzie mówimy)", value=config.PODIUM_URL, inline=False)
    embed.add_field(name="🎮 Gra", value=f"[Roblox – Parlament]({config.ROBLOX_URL})", inline=False)
    for key in STATUS_ORDER:
        ids = [uid for uid, st in s["rsvp"].items() if st == key]
        embed.add_field(
            name=f"{STATUS_LABELS[key]} ({len(ids)})",
            value=utils.mentions(ids, 900) or "—",
            inline=True,
        )
    embed.set_footer(
        text="Odpowiedź można wybrać tylko raz (na kanale lub w PV). "
        "Przypomnienia przyjdą godzinę i 15 minut przed startem."
    )
    return embed


def dm_content(s: dict, member: discord.Member, *, reminder: bool, status: Optional[str]) -> str:
    ts = int(s["start_ts"])
    if reminder:
        header = f"⏰ **Przypomnienie – posiedzenie: {s['title']}**"
    else:
        header = f"🏛️ **Nowe posiedzenie: {s['title']}**"
    lines = [f"{member.mention} {header}", f"<t:{ts}:F> (<t:{ts}:R>)"]
    if s.get("desc"):
        lines.append(s["desc"])
    lines += [
        f"📅 Wydarzenie: {s['event_url']}",
        f"📍 Podium: {config.PODIUM_URL}",
        f"🎮 Gra: {config.ROBLOX_URL}",
        f"📨 Ogłoszenie: {s['jump_url']}",
        "",
    ]
    if status:
        lines.append(locked_text(status))
    else:
        lines.append("Potwierdź obecność przyciskami poniżej (odpowiedzi nie można zmienić):")
    return "\n".join(lines)


# ---------- przyciski (trwałe, działają po restarcie) ----------
class RsvpButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=r"rwp:(?P<sid>[0-9a-f]+):(?P<st>yes|maybe|late|no)",
):
    def __init__(self, sid: str, status: str):
        super().__init__(
            discord.ui.Button(
                label=BUTTON_LABELS[status],
                style=BUTTON_STYLES[status],
                custom_id=f"rwp:{sid}:{status}",
            )
        )
        self.sid = sid
        self.status = status

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match: re.Match, /):
        return cls(match["sid"], match["st"])

    async def callback(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("Posiedzenie")
        await cog.handle_rsvp(interaction, self.sid, self.status)


def rsvp_view(sid: str) -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    for st in STATUS_ORDER:
        view.add_item(RsvpButton(sid, st))
    return view


# ---------- cog ----------
class Posiedzenie(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._tasks: set[asyncio.Task] = set()

    async def cog_load(self):
        self.bot.add_dynamic_items(RsvpButton)
        self.reminder_loop.start()

    async def cog_unload(self):
        self.reminder_loop.cancel()

    # ----- logi -----
    async def log_msg(self, text: str):
        ch = self.bot.get_channel(config.LOG_CHANNEL_ID)
        if ch is None:
            log.warning("Nie widzę kanału logów %s", config.LOG_CHANNEL_ID)
            return
        try:
            await ch.send(text[:2000], allowed_mentions=NO_MENTIONS)
        except discord.HTTPException:
            log.exception("Nie udało się wysłać loga")

    def _members(self, s: dict) -> list[discord.Member]:
        guild = self.bot.get_guild(s["guild_id"])
        role = guild.get_role(config.PING_ROLE_ID) if guild else None
        return [m for m in role.members if not m.bot] if role else []

    # ----- komenda -----
    @app_commands.command(name="posiedzenie", description="Ogłoś posiedzenie z potwierdzaniem obecności")
    @app_commands.describe(
        data="Data posiedzenia, np. 12.11.2026",
        godzina="Godzina rozpoczęcia, np. 19:30 (czas polski)",
        temat="Temat posiedzenia",
        wydarzenie="Link do wydarzenia na Discordzie",
        opis="Opcjonalny opis (np. OBOWIĄZKOWE)",
    )
    @app_commands.guild_only()
    @utils.can_use()
    async def posiedzenie(
        self,
        interaction: discord.Interaction,
        data: str,
        godzina: str,
        temat: app_commands.Range[str, 1, 150],
        wydarzenie: app_commands.Range[str, 1, 200],
        opis: Optional[app_commands.Range[str, 1, 800]] = None,
    ):
        try:
            start = utils.parse_dt(data, godzina)
        except ValueError as e:
            await interaction.response.send_message(f"❌ {e}", ephemeral=True)
            return
        now = time.time()
        if start.timestamp() <= now:
            await interaction.response.send_message("❌ Ten termin już minął.", ephemeral=True)
            return

        wydarzenie = wydarzenie.strip()
        if not re.fullmatch(r"https?://\S+", wydarzenie):
            await interaction.response.send_message(
                "❌ „wydarzenie” musi być linkiem (https://discord.com/events/...).", ephemeral=True
            )
            return

        role = interaction.guild.get_role(config.PING_ROLE_ID)
        if role is None:
            await interaction.response.send_message(
                f"❌ Nie znalazłem rangi {config.PING_ROLE_ID} na tym serwerze (ustaw PING_ROLE_ID).",
                ephemeral=True,
            )
            return
        channel = self.bot.get_channel(config.ANNOUNCE_CHANNEL_ID)
        if channel is None:
            await interaction.response.send_message(
                f"❌ Nie widzę kanału ogłoszeń {config.ANNOUNCE_CHANNEL_ID} (ustaw ANNOUNCE_CHANNEL_ID).",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        sid = uuid.uuid4().hex[:12]
        s = {
            "id": sid,
            "guild_id": interaction.guild.id,
            "channel_id": channel.id,
            "title": temat,
            "desc": opis or "",
            "event_url": wydarzenie,
            "start_ts": start.timestamp(),
            "rsvp": {},
            # przypomnienia, których termin już minął, nie mają wysyłać się od razu
            "reminded": [off for off in REMINDER_OFFSETS if start.timestamp() - off < now],
            "author_id": interaction.user.id,
        }

        try:
            msg = await channel.send(
                content=role.mention,
                embed=build_embed(s),
                view=rsvp_view(sid),
                allowed_mentions=discord.AllowedMentions(roles=True),
            )
        except discord.HTTPException as e:
            await interaction.followup.send(f"❌ Nie udało się wysłać ogłoszenia: {e}", ephemeral=True)
            return

        s["message_id"] = msg.id
        s["jump_url"] = msg.jump_url
        async with lock:
            store.data[sid] = s
            store.save()

        members = self._members(s)
        await interaction.followup.send(
            f"✅ Ogłoszenie opublikowane: {msg.jump_url}\nWysyłam PV do {len(members)} osób…", ephemeral=True
        )
        await self.log_msg(
            f"📣 <@{interaction.user.id}> utworzył posiedzenie **{temat}** "
            f"(termin <t:{int(s['start_ts'])}:F>)\n{msg.jump_url}"
        )

        task = asyncio.create_task(self.send_initial_dms(s, members))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def send_initial_dms(self, s: dict, members: list[discord.Member]):
        sent, failed = 0, []
        for m in members:
            ok = await utils.try_dm(
                m,
                content=dm_content(s, m, reminder=False, status=None),
                view=rsvp_view(s["id"]),
            )
            if ok:
                sent += 1
            else:
                failed.append(m.id)
            await asyncio.sleep(0.5)
        text = f"📨 PV o posiedzeniu **{s['title']}**: wysłano {sent}, nieudane {len(failed)}"
        if failed:
            text += f"\nNie dostali (zablokowane PV): {utils.mentions(failed, 1200)}"
        await self.log_msg(text)

    # ----- odpowiedzi -----
    async def handle_rsvp(self, interaction: discord.Interaction, sid: str, status: str):
        in_dm = interaction.guild is None
        uid = str(interaction.user.id)

        async with lock:
            s = store.data.get(sid)
            if s is None:
                await interaction.response.send_message("❌ Nie znam tego posiedzenia (mogło wygasnąć).", ephemeral=True)
                return
            if time.time() > s["start_ts"] + 6 * 3600:
                await interaction.response.send_message("To posiedzenie już się zakończyło.", ephemeral=True)
                return
            prev = s["rsvp"].get(uid)
            if prev is None:
                s["rsvp"][uid] = status
                store.save()

        # odpowiedź już była: nie można zmienić
        if prev is not None:
            if in_dm:
                await interaction.response.edit_message(
                    content=_with_lock(interaction.message.content, locked_text(prev)), view=None
                )
            else:
                await interaction.response.send_message(locked_text(prev), ephemeral=True)
            return

        if in_dm:
            await interaction.response.edit_message(
                content=_with_lock(interaction.message.content, locked_text(status)), view=None
            )
            await self.refresh_announcement(s)
        else:
            await interaction.response.edit_message(embed=build_embed(s))
            await interaction.followup.send(locked_text(status).replace("Już odpowiedziałeś", "Zapisano"), ephemeral=True)

        where = "w PV" if in_dm else "na kanale"
        await self.log_msg(
            f"📝 <@{uid}> ({interaction.user}) odpowiedział **{STATUS_LABELS[status]}** "
            f"na „{s['title']}” ({where})"
        )

    async def refresh_announcement(self, s: dict):
        ch = self.bot.get_channel(s["channel_id"])
        if ch is None:
            return
        try:
            await ch.get_partial_message(s["message_id"]).edit(embed=build_embed(s))
        except discord.HTTPException:
            log.exception("Nie udało się odświeżyć ogłoszenia")

    # ----- przypomnienia -----
    @tasks.loop(seconds=30)
    async def reminder_loop(self):
        try:
            now = time.time()
            for sid, s in list(store.data.items()):
                if now > s["start_ts"] + 7 * 86400:
                    async with lock:
                        store.data.pop(sid, None)
                        store.save()
                    continue
                due = [o for o in REMINDER_OFFSETS if o not in s["reminded"] and now >= s["start_ts"] - o]
                if not due:
                    continue
                async with lock:
                    s["reminded"].extend(due)
                    store.save()
                if now <= s["start_ts"]:
                    # gdyby bot był wyłączony, wyślij tylko jedno (najbliższe) przypomnienie
                    await self.send_reminders(s, min(due))
        except Exception:
            log.exception("Błąd w pętli przypomnień")

    @reminder_loop.before_loop
    async def _wait(self):
        await self.bot.wait_until_ready()

    async def send_reminders(self, s: dict, offset: int):
        sent = failed = 0
        failed_ids = []
        for m in self._members(s):
            status = s["rsvp"].get(str(m.id))
            if status == "no":
                continue
            kwargs = {"content": dm_content(s, m, reminder=True, status=status)}
            if status is None:
                kwargs["view"] = rsvp_view(s["id"])  # niezdecydowani dostają przyciski
            if await utils.try_dm(m, **kwargs):
                sent += 1
            else:
                failed += 1
                failed_ids.append(m.id)
            await asyncio.sleep(0.5)
        label = "1 godz." if offset == 3600 else "15 min"
        text = f"⏰ Przypomnienie ({label}) – **{s['title']}**: wysłano {sent}, nieudane {failed}"
        if failed_ids:
            text += f"\nNie dostali: {utils.mentions(failed_ids, 1200)}"
        log.info(text)
        await self.log_msg(text)


def _with_lock(content: str, lock_line: str) -> str:
    return f"{content}\n\n{lock_line}"[:2000]


async def setup(bot: commands.Bot):
    await bot.add_cog(Posiedzenie(bot))
