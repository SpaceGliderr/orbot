import asyncio
import re
from operator import itemgetter
from typing import List

import discord
import tweepy
from requests import Response

from src.cogs.content_poster.ui import PersistentTweetView, TweetDetails
from src.utils.helper import (
    convert_files_to_zip,
    dict_has_key,
    download_files,
    get_from_dict,
)


class TwitterHelper:
    url_postfix = ":orig"

    @staticmethod
    def get_media_urls(media_objects: List[dict]):
        urls = []
        filenames = []
        for media_object in media_objects:
            if media_object["type"] == "photo":
                filename = media_object["url"].split("/")[-1]

                urls.append(f"{media_object['url']}{TwitterHelper.url_postfix}")
                filenames.append(filename)
            else:
                variants = [variant for variant in media_object["variants"] if dict_has_key(variant, "bit_rate")]
                highest_bit_rate_variant = max(variants, key=itemgetter("bit_rate"))

                filename = highest_bit_rate_variant["url"].split("/")[-1]
                filename = re.sub(r"\?.+", "", filename)

                urls.append(highest_bit_rate_variant["url"])
                filenames.append(filename)
        return urls, filenames

    @staticmethod
    def get_items_per_post(items: list, items_per_post: int = 10):
        return [items[i : i + items_per_post] for i in range(0, len(items), items_per_post)]

    @staticmethod
    async def parse_response_object(tweets: Response):
        tweet: tweepy.Tweet = tweets.data[0].data

        urls = tweet["entities"]["urls"][-1]
        expanded_url = urls["expanded_url"]
        tweet_url = urls["url"]

        media_urls, media_filenames = TwitterHelper.get_media_urls([media.data for media in tweets.includes["media"]])

        urls_per_post = TwitterHelper.get_items_per_post(media_urls)
        filenames_per_post = TwitterHelper.get_items_per_post(media_filenames)

        metadata = {
            "user": tweets.includes["users"][0],
            "tweet_url": expanded_url.rsplit("/", 2)[0],
            "conversation_id": tweet["conversation_id"],
            "tweet_text": tweet["text"].replace(tweet_url, ""),
        }

        return urls_per_post, filenames_per_post, metadata

    @staticmethod
    async def parse_response_raw_data(tweets: dict):
        urls = get_from_dict(tweets[0], ["data", "entities", "urls"])[
            -1
        ]  # Take the last one because it is the link to the Tweet
        expanded_url = urls["expanded_url"]
        tweet_url = urls["url"]

        media_urls = []
        media_filenames = []
        for tweet in tweets:
            medias = get_from_dict(tweet, ["includes", "media"])
            urls, filenames = TwitterHelper.get_media_urls(medias)

            media_urls.extend(urls)
            media_filenames.extend(filenames)

        urls_per_post = TwitterHelper.get_items_per_post(media_urls)
        filenames_per_post = TwitterHelper.get_items_per_post(media_filenames)

        metadata = {
            "user": get_from_dict(tweets[0], ["includes", "users"])[0],
            "tweet_url": expanded_url.rsplit("/", 2)[0],  # Removes the /photo/1 or /media/1 postfixes
            "conversation_id": get_from_dict(tweets[0], ["data", "conversation_id"]),
            "tweet_text": get_from_dict(tweets[0], ["data", "text"]).replace(tweet_url, ""),
        }

        return urls_per_post, filenames_per_post, metadata

    @staticmethod
    async def send_post(
        user: dict,
        tweet_text: str,
        urls: List[str],
        tweet_url: str,
        conversation_id: str,
        media_filenames: List[str],
        client: discord.Client,
        channel: discord.TextChannel,
    ):
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
        message = await channel.send(content=content, files=files)

        # The following RegEx expression serves to obtain the Tweet URL from the caption
        tweet_details: TweetDetails = {"user": user, "url": tweet_url}

        # Generate the ZIP file and send it as a separate message
        zip_file = await convert_files_to_zip(files, str(conversation_id))

        # Update the message with the PersistentTweetView
        view = PersistentTweetView(message=message, files=files, bot=client, tweet_details=tweet_details)
        client.add_view(view=view)

        await asyncio.gather(channel.send(file=zip_file), message.edit(view=view))
