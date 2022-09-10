import asyncio

import asyncpg
import discord
from discord.ext import commands

from .config import TOKEN
from os import walk


intents = discord.Intents(
    guilds=True,
    members=True,
    messages=True,
    guild_reactions=True,
    guild_messages=True,
    message_content=True,
)


class Orbot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=">", case_insensitive=True, intents=intents)
        self.exts = ["jishaku"]
        self.cogs_path = "src/cogs"
        self.cogs_ext_prefix = "src.cogs."


    def run(self):
        super().run(TOKEN)


    async def start(self, *args, **kwargs):
        # self.pool = None

        await self.load_extensions()

        # while not self.pool:
        #     try:
        #         self.pool = await asyncpg.create_pool(user="postgres", host="db")
        #     except asyncpg.exceptions.CannotConnectNowError or ConnectionRefusedError:
        #         await asyncio.sleep(1)

        await super().start(*args, **kwargs)


    async def load_extensions(self):
        cogs = map(lambda cog: f"{self.cogs_ext_prefix}{cog}", [filename.split('.', 1)[0] for filename in next(walk(self.cogs_path), (None, None, []))[2]])

        extensions = list(cogs) + self.exts

        for extension in extensions:
            await self.load_extension(extension)
