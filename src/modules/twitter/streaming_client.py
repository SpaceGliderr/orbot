import asyncio
import json
import logging
import os

import discord
from tweepy.asynchronous import AsyncStreamingClient

from src.modules.twitter.twitter import TwitterHelper
from src.utils.config import ContentPosterConfig
from src.utils.helper import dict_has_key, get_from_dict


class TwitterStreamingClient(AsyncStreamingClient):
    """A class to initialise the `AsyncStreamingClient` object from the Twitter API.

    Parameters
    ----------
        * client: :class:`discord.Client`
            - The client instance that will be used to send messages.
    """

    url_postfix = ":orig"

    def __init__(self, client: discord.Client):
        # The `wait_on_rate_limit` argument prevents the streaming client from shutting off when the API rate limit is reached
        super().__init__(bearer_token=os.getenv("TWITTER_BEARER_TOKEN"), wait_on_rate_limit=True, max_retries=5)
        self.client = client
        self.channel = ContentPosterConfig().get_feed_channel(self.client)
        self.tweets = {}
        self.status = ""

    def is_valid_tweet(self, tweet: dict):
        """A function that checks whether the Tweets hashtag passes the hashtag filter.

        Parameters
        ----------
            * tweet: :class:`dict`
                - The Tweet to filter.
        """
        hashtag_filters = ContentPosterConfig().hashtag_filters

        hashtags = get_from_dict(tweet, ["data", "entities", "hashtags"])

        if hashtags is not None:
            whitelisted_tags = []
            blacklisted_tags = []

            for hashtag_metadata in hashtags:
                tag = get_from_dict(hashtag_metadata, ["tag"]).lower()
                whitelisted_tags.append(tag in hashtag_filters["whitelist"])
                blacklisted_tags.append(tag in hashtag_filters["blacklist"])

            return not any(blacklisted_tags) and any(whitelisted_tags)
        return False

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

        urls_per_post, filenames_per_post, metadata = await TwitterHelper.parse_response_raw_data(tweets)

        del self.tweets[conversation_id]

        for idx, post_urls in enumerate(urls_per_post):
            loop = asyncio.get_event_loop()
            loop.create_task(
                TwitterHelper.send_post(
                    urls=post_urls,
                    media_filenames=filenames_per_post[idx],
                    client=self.client,
                    channel=self.channel,
                    **metadata
                )
            )

    async def on_connect(self):
        logging.info("Twitter stream has been connected successfully")
        self.status = "connected"

    async def on_disconnect(self):
        logging.info("Twitter stream has been disconnected successfully")
        self.status = "disconnected"

    async def on_request_error(self, status_code):
        if status_code == 429:
            self.status = "retrying"
        else:
            self.status = "unknown"

    async def on_data(self, raw_data):
        """Triggered when data is received from the stream."""
        if self.channel is None:
            return

        data = json.loads(raw_data)

        # The conversation ID is a unique identifier used to identify which tweets belong to the same Twitter thread
        # Therefore, it is used as the dictionary key to reconstruct the Twitter thread
        # Reconstructing the thread is important to tell which images belong to the same event
        conversation_id = get_from_dict(data, ["data", "conversation_id"])

        # Checks whether the Twitter thread has been recorded before
        if dict_has_key(self.tweets, conversation_id):
            self.tweets[conversation_id].append(data)
        elif self.is_valid_tweet(data):
            self.tweets[conversation_id] = [data]

            # The following runs asynchronous tasks in a coroutine so that it doesn't block the main event loop
            loop = asyncio.get_event_loop()
            loop.create_task(self.compile_tweets(conversation_id))
