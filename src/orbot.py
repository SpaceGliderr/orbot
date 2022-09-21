import asyncio

import asyncpg
import discord
from discord.ext import commands
from discord import app_commands

import os


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


    def run(self):
        super().run(os.getenv('TOKEN'))


    async def start(self, *args, **kwargs):
        # self.pool = None

        await self.load_extensions()

        # while not self.pool:
        #     try:
        #         self.pool = await asyncpg.create_pool(user="postgres", host="db")
        #     except asyncpg.exceptions.CannotConnectNowError or ConnectionRefusedError:
        #         await asyncio.sleep(1)

        await super().start(*args, **kwargs)

    
    async def setup_hook(self):
        self.tree.copy_global_to(guild=MY_GUILD)
        await self.tree.sync(guild=MY_GUILD)


    async def load_extensions(self):
        cogs = map(lambda cog: f"{self.cogs_ext_prefix}{cog}.{cog}", [dirname.split('.', 1)[0] for dirname in next(os.walk(self.cogs_path), (None, None, []))[1] if dirname.split('.', 1)[0] not in ["__pycache__"]])

        extensions = list(cogs) + self.exts

        for extension in extensions:
            await self.load_extension(extension)
