import asyncio
import json
import logging
import os
import re
from operator import itemgetter

import discord
from tweepy.asynchronous import AsyncStreamingClient

from src.cogs.content_poster.ui import PersistentTweetView, TweetDetails
from src.utils.config import ContentPosterConfig
from src.utils.helper import (
    convert_files_to_zip,
    dict_has_key,
    download_files,
    get_from_dict,
)


class TwitterStreamingClient(AsyncStreamingClient):
    url_postfix = ":orig"

    def __init__(self, client: discord.Client):
        # The `wait_on_rate_limit` argument prevents the streaming client from shutting off when the API rate limit is reached
        super().__init__(bearer_token=os.getenv("TWITTER_BEARER_TOKEN"), wait_on_rate_limit=True, max_retries=5)
        self.client = client
        self.channel = ContentPosterConfig().get_feed_channel(self.client)
        self.tweets = {}

    def is_valid_tweet(self, tweet):
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

    def get_media_urls(self, media_objects):
        urls = []
        filenames = []
        for media_object in media_objects:
            if media_object["type"] == "photo":
                filename = media_object["url"].split("/")[-1]

                urls.append(f"{media_object['url']}{self.url_postfix}")
                filenames.append(filename)
            else:
                variants = [variant for variant in media_object["variants"] if dict_has_key(variant, "bit_rate")]
                highest_bit_rate_variant = max(variants, key=itemgetter("bit_rate"))

                filename = highest_bit_rate_variant["url"].split("/")[-1]
                filename = re.sub(r"\?.+", "", filename)

                urls.append(highest_bit_rate_variant["url"])
                filenames.append(filename)
        return urls, filenames

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
        urls = get_from_dict(tweets[0], ["data", "entities", "urls"])[
            -1
        ]  # Take the last one because it is the link to the Tweet

        expanded_url = urls["expanded_url"]
        tweet_url = urls["url"]

        expanded_tweet_url = expanded_url.rsplit("/", 2)[0]  # Removes the /photo/1 or /media/1 postfixes
        tweet_text_no_url = tweet_text.replace(tweet_url, "")

        urls = []
        filenames = []
        for tweet in tweets:
            medias = get_from_dict(tweet, ["includes", "media"])
            media_urls, media_filenames = self.get_media_urls(medias)

            urls.extend(media_urls)
            filenames.extend(media_filenames)

        del self.tweets[conversation_id]

        urls_per_post = [urls[i : i + 10] for i in range(0, len(urls), 10)]
        filenames_per_post = [filenames[i : i + 10] for i in range(0, len(filenames), 10)]

        for idx, post_urls in enumerate(urls_per_post):
            loop = asyncio.get_event_loop()
            loop.create_task(
                self.send_post(
                    user, tweet_text_no_url, post_urls, expanded_tweet_url, conversation_id, filenames_per_post[idx]
                )
            )

    async def send_post(self, user, tweet_text, urls, tweet_url, conversation_id, media_filenames):
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
        files = await download_files(urls, media_filenames)

        # Post the Twitter message to the feed channel
        embedless_urls = [f"<{url}>" for url in urls]

        if len(tweet_text) != 0:
            tweet_text = f"{tweet_text}\n"

        content = (
            f"```ml\nOriginal Tweet````{user['name']} @{user['username']}`\n{tweet_text}<{tweet_url}>\n\n```ml\nUploaded Media Links```"
            + "\n".join(embedless_urls)
        )
        message = await self.channel.send(content=content, files=files)

        # The following RegEx expression serves to obtain the Tweet URL from the caption
        tweet_details: TweetDetails = {"user": user, "url": tweet_url}

        # Generate the ZIP file and send it as a separate message
        zip_file = await convert_files_to_zip(files, str(conversation_id))

        # Update the message with the PersistentTweetView
        view = PersistentTweetView(message=message, files=files, bot=self.client, tweet_details=tweet_details)
        self.client.add_view(view=view)

        await asyncio.gather(self.channel.send(file=zip_file), message.edit(view=view))

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
        elif self.is_valid_tweet(data):
            self.tweets[conversation_id] = [data]

            # The following runs asynchronous tasks in a coroutine so that it doesn't block the main event loop
            loop = asyncio.get_event_loop()
            loop.create_task(self.compile_tweets(conversation_id))
