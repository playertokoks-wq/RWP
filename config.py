import os
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()


def _int(name: str, default=None):
    raw = os.getenv(name, "").strip()
    return int(raw) if raw.isdigit() else default


TZ = ZoneInfo("Europe/Warsaw")

# Logo partii (dołączane do ogłoszenia jako miniatura)
LOGO_PATH = Path(__file__).parent / "assets" / "logo.png"
LOGO_FILENAME = "logo.png"

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = _int("GUILD_ID")

# Na Railway ustaw DATA_DIR=/data i podepnij Volume pod /data (inaczej dane znikają przy deployu)
DATA_DIR = os.getenv("DATA_DIR", "data")

PARTY_NAME = os.getenv("PARTY_NAME", "Ruch Wolnych Polaków")

# Stałe linki
ROBLOX_URL = os.getenv("ROBLOX_URL", "https://www.roblox.com/pl/games/137566618719844/Parlament")
PODIUM_URL = os.getenv(
    "PODIUM_URL", "https://discord.com/channels/1432207073025855580/1432298052252860518"
)

# Ranga pingowana w ogłoszeniu. Członkowie tej rangi dostają też PV z przyciskami.
PING_ROLE_ID = _int("PING_ROLE_ID", 1523301940853870653)

# /posiedzenie mogą używać tylko osoby z uprawnieniem Administrator (patrz utils.can_use)

# Kanał ogłoszeń i kanał logów
ANNOUNCE_CHANNEL_ID = _int("ANNOUNCE_CHANNEL_ID", 1523311020117065888)
LOG_CHANNEL_ID = _int("LOG_CHANNEL_ID", 1523326084106682369)

# --- Dyscyplina głosowań (/dyscyplina) ---
DISCIPLINE_CHANNEL_ID = _int("DISCIPLINE_CHANNEL_ID", 1523311146428399686)
DISCIPLINE_PING_ROLE_ID = _int("DISCIPLINE_PING_ROLE_ID", 1523301940853870653)
DISCIPLINE_HEADER_EMOJI = os.getenv("DISCIPLINE_HEADER_EMOJI", "<:a05645312e5f44b79771207688ef48c4:1532323745333514461>")
# Emoji przy decyzji. Dla PRZECIW i WSTRZYMUJĘ SIĘ wpisz własne (<:nazwa:ID>) – tu są zwykłe zastępcze.
DISCIPLINE_EMOJIS = {
    "ZA": "<:__:1530614794393223188>",
    "WOLNA RĘKA": "<:shield:1528743057292529724>",
    "PRZECIW": "❌",
    "WSTRZYMUJĘ SIĘ": "⚪",
}