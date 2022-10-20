import asyncio
import json
import logging
import os
import re

import discord
from tweepy.asynchronous import AsyncStreamingClient

from src.cogs.content_poster.ui import PersistentTweetView, TweetDetails
from src.utils.config import ContentPosterConfig
from src.utils.helper import convert_files_to_zip, dict_has_key, download_files, get_from_dict


class TwitterStreamingClient(AsyncStreamingClient):
    url_postfix = ":orig"

    def __init__(self, client: discord.Client):
        # The `wait_on_rate_limit` argument prevents the streaming client from shutting off when the API rate limit is reached
        super().__init__(bearer_token=os.getenv("TWITTER_BEARER_TOKEN"), wait_on_rate_limit=True, max_retries=5)
        self.client = client
        self.channel = ContentPosterConfig().get_feed_channel(self.client)
        self.tweets = {}

    async def compile_tweets(self, conversation_id: str, delay: float = 10):
        """A delayed function to compile the Tweets from a Tweet thread.
        
        Parameters
        ----------
            * conversation_id: :class:`str`
                - The Twitter thread to track.
            * delay: :class:`float` | 10
                - The duration to wait before compiling the tweets.
        """
        await asyncio.sleep(delay)

        tweets = self.tweets[conversation_id]

        user = get_from_dict(tweets[0], ["includes", "users"])[0]
        tweet_text = get_from_dict(tweets[0], ["data", "text"])

        urls = []
        for tweet in tweets:
            medias = get_from_dict(tweet, ["includes", "media"])
            urls.extend([f"{media['url']}{self.url_postfix}" for media in medias])

        del self.tweets[conversation_id]

        urls_per_post = [urls[i:i+10] for i in range(0,len(urls),10)]

        for post_urls in urls_per_post:
            loop = asyncio.get_event_loop()
            loop.create_task(self.send_post(user, tweet_text, post_urls))

    async def send_post(self, user, tweet_text, urls):
        """Sends a post with a PersistentTweetView to the feed channel.
        
        Parameters
        ----------
            * user: :class:`dict`
                - The user ID to be appended onto the `rule_content` string.
            * tweet_text: :class:`str`
                - The list of remaining user IDs to add.
            * urls: List[:class:`str`]
                - The current rule content string.
        """
        # Download the files from the URL
        files = await download_files(urls)

        # Post the Twitter message to the feed channel
        embedless_urls = [f"<{url}>" for url in urls]
        content = f"`@{user['username']}`\n<{tweet_text}>\n" + "\n".join(embedless_urls)
        message = await self.channel.send(content=content, files=files)

        # The following RegEx expression serves to obtain the Tweet URL from the caption
        url = re.search(r"https://t.co/\S+", tweet_text)
        tweet_details: TweetDetails = {"user": user, "url": url.group()}

        # Generate the ZIP file and send it as a separate message
        zip_file = await convert_files_to_zip(files, url.group()[13:])
        # await self.channel.send(file=zip_file)

        # Update the message with the PersistentTweetView
        view = PersistentTweetView(message_id=message.id, files=files, bot=self.client, tweet_details=tweet_details)
        self.client.add_view(view=view)

        await asyncio.gather(
            self.channel.send(file=zip_file),
            message.edit(view=view)
        )
        # await message.edit(view=view)

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

        # The conversation ID is a unique identifier used to identify which tweets belong to the same Twitter thread
        # Therefore, it is used as the dictionary key to reconstruct the Twitter thread
        # Reconstructing the thread is important to tell which images belong to the same event
        conversation_id = get_from_dict(data, ["data", "conversation_id"]) 

        # Checks whether the Twitter thread has been recorded before
        if dict_has_key(self.tweets, conversation_id):
            self.tweets[conversation_id].append(data)
        else:
            self.tweets[conversation_id] = [data]

            # The following runs asynchronous tasks in a coroutine so that it doesn't block the main event loop
            loop = asyncio.get_event_loop()
            loop.create_task(self.compile_tweets(conversation_id))
