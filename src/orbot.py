import logging
import os

import discord
from discord.ext import commands

from src.cogs.content_poster.fansite import FansiteFeed
from src.cogs.role_picker.ui import PersistentRolePickerView

intents = discord.Intents(
    guilds=True,
    members=True,
    messages=True,
    guild_reactions=True,
    guild_messages=True,
    message_content=True,
)

MY_GUILD = discord.Object(id=864118528134742026)


class Orbot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=">", case_insensitive=True, intents=intents)
        self.exts = ["jishaku"]
        self.cogs_path = "src/cogs"
        self.cogs_ext_prefix = "src.cogs."
        self.twitter_stream = None

    def run(self):
        super().run(os.getenv("DEV_TOKEN"))

    async def start(self, *args, **kwargs):
        await self.load_extensions()
        await super().start(*args, **kwargs)

    async def close(self):
        if self.twitter_stream is not None and self.twitter_stream.stream is not None:
            await self.twitter_stream.close()

        logging.info("Orbot is shutting down... Goodbye!")
        await super().close()

    async def setup_hook(self):
        self.add_view(PersistentRolePickerView())
        self.tree.copy_global_to(guild=MY_GUILD)
        await self.tree.sync(guild=MY_GUILD)

    async def load_extensions(self):
        cogs = map(
            lambda cog: f"{self.cogs_ext_prefix}{cog}.{cog}",
            [
                dirname.split(".", 1)[0]
                for dirname in next(os.walk(self.cogs_path), (None, None, []))[1]
                if dirname.split(".", 1)[0] not in ["__pycache__"]
            ],
        )

        extensions = list(cogs) + self.exts

        for extension in extensions:
            await self.load_extension(extension)

    async def on_ready(self):
        self.twitter_stream = await FansiteFeed.init_then_start(client=self)
        logging.info("Orbot is ready")


client = Orbot()
