import asyncio

import asyncpg
import discord
from discord.ext import commands

from .config import TOKEN


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

    def run(self):
        super().run(TOKEN)

    async def start(self, *args, **kwargs):
        # self.pool = None

        extensions = ["jishaku"]

        for extension in extensions:
            await self.load_extension(extension)

        # while not self.pool:
        #     try:
        #         self.pool = await asyncpg.create_pool(user="postgres", host="db")
        #     except asyncpg.exceptions.CannotConnectNowError or ConnectionRefusedError:
        #         await asyncio.sleep(1)

        await super().start(*args, **kwargs)
