import logging
import os

import discord
from discord.ext import commands

from src.cogs.content_poster.ui.views.persistent import PersistentTweetView
from src.cogs.role_picker.ui import PersistentRolePickerView
from src.modules.twitter.feed import TwitterFeed
from src.utils.config import ContentPosterConfig

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
        await self.reactivate_persistent_views()
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
        self.twitter_stream = await TwitterFeed.init_then_start(client=self)
        logging.info("Orbot is ready")

    async def reactivate_persistent_views(self):
        cp_conf = ContentPosterConfig()

        active_posts = cp_conf.active_posts
        feed_channel_id = cp_conf.data["config"]["feed_channel_id"]

        if feed_channel_id is None:
            return

        channel = await self.fetch_channel(feed_channel_id)

        for msg_id, tweet_details in active_posts.items():
            message = await channel.fetch_message(msg_id)
            files = [await attachment.to_file() for attachment in message.attachments]

            self.add_view(PersistentTweetView(message=message, files=files, tweet_details=tweet_details, bot=self))


client = Orbot()
