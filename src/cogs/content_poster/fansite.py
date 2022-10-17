import asyncio
import json
import logging
import os
import re
from typing import List, Literal

import discord
import tweepy
from tweepy.asynchronous import AsyncStreamingClient

from src.cogs.content_poster.ui import PersistentTweetView, TweetDetails
from src.utils.config import ContentPosterConfig
from src.utils.helper import convert_files_to_zip, download_files, get_from_dict


class FansiteStreamingClient(AsyncStreamingClient):
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


class FansiteFeed:
    # Static class variables
    rule_prefix = "(from:"
    rule_postfix = ") has:media"
    rule_connector = " OR from:"
    max_rule_content_length = 512 - (len(rule_prefix) + len(rule_postfix))

    def __init__(self, client: discord.Client):
        # self.follow = self.get_user_ids()
        self.follow = ["1578046589578661888"]  # ! Remove this once the testing is complete
        self.follow_change_flag = False # This flag indicates whether the follow list needs to be refreshed on Stream restart
        self.stream: FansiteStreamingClient = None

        self.client: discord.Client = client

    @classmethod
    async def init_then_start(cls, client: discord.Client):
        """A class method that initializes an instance of `FansiteFeed` and then starts a Twitter stream."""
        feed = cls(client)
        await feed.start()
        return feed

    @staticmethod
    def get_user_ids():
        """Gets the Twitter user IDs of fansites that the `StreamingClient` listens to."""
        with open("src/data/IDs.txt") as data:
            lines = data.read().splitlines()
            return [user_id for user_id in lines]

    def save_user_id(self, user_id: str, purpose: Literal["add", "remove"]):
        """Adds or removes a Twitter user ID to the `IDs.txt` file.
        
        Parameters
        ----------
            * user_id: :class:`str`
                - The user ID to be appended onto the `rule_content` string.
            * purpose: Literal[`add`, `remove`]
                - The action to perform on the user ID.
        """
        with open("src/data/IDs.txt", "r+") as data:
            lines = data.read().splitlines()
            data.seek(0)  # Moves the file pointer to the first index so it replaces the content

            if purpose == "remove":
                lines.remove(user_id)
            elif purpose == "add":
                lines.append(user_id)

            data.write("\n".join(lines))  # Adds newlines between IDs
            data.truncate()  # Removes the extra lines at the end of the file

        self.follow = self.get_user_ids()
        self.follow_change_flag = True

    def generate_rule_contents(
        self, user_id: str, user_ids: List[str], rule_content: str = "", rule_contents: List[str] = []
    ):
        """
        A recursive function that generates rule contents based on the Twitter user IDs. 
        Only 25 `StreamRule`s with content lengths of 512 characters are allowed per `Stream`. 
        This recursive function ensures that these requirements are met.

        Parameters
        ----------
            * user_id: :class:`str`
                - The user ID to be appended onto the `rule_content` string.
            * user_ids: List[:class:`str`]
                - The list of remaining user IDs to add.
            * rule_content: `str` | `""`
                - The current rule content string.
            * rule_contents: List[`str`] | `[]`
                - The list of completed rule contents.
        """
        # Add the next user ID to the rule content
        content = f"{user_id}" if rule_content == "" else f"{self.rule_connector}{user_id}"
        temp_rule_content = f"{rule_content}{content}"

        if len(user_ids) == 0: 
            # If there are no more User IDs, append the rule content to the array and end the recursive loop
            rule_contents.append(f"{self.rule_prefix}{temp_rule_content}{self.rule_postfix}")
            return rule_contents
        
        if len(temp_rule_content) >= self.max_rule_content_length:
            # If the new rule content exceeds 512 characters, append the old rule content and use the current user ID in the next recursion
            rule_contents.append(f"{self.rule_prefix}{rule_content}{self.rule_postfix}")
            return self.generate_rule_contents(user_id, user_ids, rule_contents=rule_contents)
        else:
            # Otherwise, append the new rule content and use the next user ID in the next recursion
            next_user_id = user_ids.pop(0)
            return self.generate_rule_contents(next_user_id, user_ids, temp_rule_content, rule_contents)

    def generate_stream_rules(self):
        """Generates a list of `StreamRule`s by using the rule contents generated by `generate_rule_contents` method."""
        user_ids = self.follow.copy() # Copy this to prevent it from mutating the follow list
        first_user_id = user_ids.pop(0)
        rule_contents = self.generate_rule_contents(first_user_id, user_ids)
        return [tweepy.StreamRule(rule_content) for rule_content in rule_contents]

    async def clear_all_stream_rules(self):
        """Deletes the `StreamRule`s that the current `Stream` has."""
        current_rules = await self.stream.get_rules()
        if self.stream is not None and current_rules.data is not None:
            await self.stream.delete_rules([rule.id for rule in current_rules.data])

    async def start(self):
        """Starts the `FansiteStreamingClient`."""
        self.stream = FansiteStreamingClient(self.client) # ! Can't setup more than 1 stream concurrently if there are more than a certain amount of user IDs

        current_rules = await self.stream.get_rules()
        if current_rules.data is None or self.follow_change_flag: 
            # Only regenerate stream rules if there are no current rules or the follow list has been changed
            await self.clear_all_stream_rules()
            await self.stream.add_rules(self.generate_stream_rules())

        self.stream.filter(
            tweet_fields=["attachments"],
            media_fields=["url"],
            user_fields=["name", "username"],
            expansions=["attachments.media_keys", "author_id"],
        )  # Don't need await so it doesn't block the main loop execution

    async def close(self):
        """Closes the stream."""
        if self.stream is not None:
            self.stream.disconnect()  # Doesn't force a direct disconnection as it waits until the next cycle in the event loop to disconnect
            await self.stream.session.close()  # Close the websocket connection to Twitter's API - this forces a direct disconnection
            self.stream = None

    async def restart(self):
        """Restarts the stream."""
        await self.close()
        await self.start(self.client)
