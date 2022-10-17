import asyncio
import json
import logging
import os
import re

import discord
from tweepy.asynchronous import AsyncStreamingClient

from src.cogs.content_poster.ui import PersistentTweetView, TweetDetails
from src.utils.config import ContentPosterConfig
from src.utils.helper import convert_files_to_zip, download_files, get_from_dict


class TwitterStreamingClient(AsyncStreamingClient):
    def __init__(self, client: discord.Client):
        # The `wait_on_rate_limit` argument prevents the streaming client from shutting off when the API rate limit is reached
        super().__init__(bearer_token=os.getenv("TWITTER_BEARER_TOKEN"), wait_on_rate_limit=True, max_retries=5)
        self.client = client
        self.channel = ContentPosterConfig().get_feed_channel(self.client)

    async def send_post(self, data):
        """Sends a post with a PersistentTweetView to the feed channel."""
        # Get all the required information from the incoming data
        medias = get_from_dict(data, ["includes", "media"])
        user = get_from_dict(data, ["includes", "users"])[0]
        tweet_text = get_from_dict(data, ["data", "text"])
        urls = [media["url"] for media in medias]

        # Download the files from the URL and create a ZIP file
        files = await download_files(urls)
        zip_file = await convert_files_to_zip(files)
        feed_channel_files = [*files, zip_file]  # Combines the Media and ZIP files, only posted in the feed channel

        # Post the Twitter message to the feed channel
        message = await self.channel.send(content=user["name"], files=feed_channel_files)

        # The following for loop is to make it so that the Discord files are read from the first byte again after being sent as a message earlier
        # Being sent as a message initially means the byte-file pointer is at the end
        files = list(map(lambda f: f.fp.seek(0), files))
        # ? Maybe use a more elegant method here instead of a for loop
        # for f in files:
        #     f.fp.seek(0)

        # The following RegEx expression serves to obtain the Tweet URL from the caption
        url = re.search(r"https://t.co/\S+", tweet_text)
        tweet_details: TweetDetails = {"user": user, "url": url.group()}

        # Update the message with the PersistentTweetView
        view = PersistentTweetView(message_id=message.id, files=files, bot=self.client, tweet_details=tweet_details)
        self.client.add_view(view=view)
        await message.edit(view=view)

        # Once the user is done with the PersistentTweetView, remove the view from the original message
        await view.wait()
        await message.edit(view=None)  # ? Maybe move this to the `Stop` button in the UI file

    async def on_connect(self):
        logging.info("Twitter stream has been connected successfully")

    async def on_disconnect(self):
        logging.info("Twitter stream has been disconnected successfully")

    async def on_data(self, raw_data):
        """Triggered when data is received from the stream."""
        data = json.loads(raw_data)

        # The following runs asynchronous tasks in a coroutine so that it doesn't block the main event loop
        loop = asyncio.get_event_loop()
        loop.create_task(self.send_post(data))
