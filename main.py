import logging

import discord
from discord import app_commands
from discord.ext import commands

import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("rwp-bot")

EXTENSIONS = ["cogs.posiedzenie"]


class RwpBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True  # wymagane: lista członków rangi i wysyłanie PV (włącz w Developer Portal)
        super().__init__(command_prefix=commands.when_mentioned, intents=intents, help_command=None)

    async def setup_hook(self):
        for ext in EXTENSIONS:
            await self.load_extension(ext)
            log.info("Załadowano %s", ext)

        if config.GUILD_ID:
            guild = discord.Object(id=config.GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
        else:
            synced = await self.tree.sync()
        log.info("Zsynchronizowano %d komend", len(synced))

    async def on_ready(self):
        log.info("Zalogowano jako %s (%s)", self.user, self.user.id)


bot = RwpBot()


@bot.tree.error
async def on_tree_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CheckFailure):
        text = str(error) or "🚫 Brak uprawnień."
    else:
        log.exception("Błąd komendy", exc_info=error)
        text = "❌ Wystąpił błąd. Spróbuj ponownie lub zgłoś to administratorowi."
    try:
        if interaction.response.is_done():
            await interaction.followup.send(text, ephemeral=True)
        else:
            await interaction.response.send_message(text, ephemeral=True)
    except discord.HTTPException:
        pass


def main():
    if not config.TOKEN:
        raise SystemExit("Brak DISCORD_TOKEN w zmiennych środowiskowych.")
    bot.run(config.TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
