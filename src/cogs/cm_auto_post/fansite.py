import asyncio
import json
import os
import re
from typing import List, Literal
import tweepy
import discord
from tweepy.asynchronous import AsyncStreamingClient
from src.cogs.cm_auto_post.ui import PersistentTweetView

from src.utils.helper import convert_files_to_zip, download_files, get_from_dict
from src.utils.config import CMAutoPostConfig


class FansiteStreamingClient(AsyncStreamingClient):
    def __init__(self, client: discord.Client):
        super().__init__(bearer_token=os.getenv("TWITTER_BEARER_TOKEN"), wait_on_rate_limit=True)
        self.client = client


    async def send_post(self, data):
        medias = get_from_dict(data, ["includes", "media"])
        user = get_from_dict(data, ["includes", "users"])[0]
        tweet_text = get_from_dict(data, ["data", "text"])
        urls = [media["url"] for media in medias]
        
        files = await download_files(urls)
        zip_file = await convert_files_to_zip(files)
        cm_list = [*files, zip_file]
        
        cmap_conf = CMAutoPostConfig()
        channel = await self.client.fetch_channel(cmap_conf.data["config"]["feed_channel_id"])
        
        message = await channel.send(content=user["name"], files=cm_list)
        
        # The following for loop is to make it so that the Discord files are read from the first byte again after being sent as a message earlier
        # Being sent as a message initially means the byte-file pointer is at the end
        # ? Maybe use a more elegant method here instead of a for loop
        for f in files:
            f.fp.seek(0)

        # Update the message with the post view
        url = re.search(r"https://t.co/\S+", tweet_text)
        tweet_details = {
            "user": user,
            "url": url.group()
        }
        view = PersistentTweetView(message_id=message.id, files=files, bot=self.client, tweet_details=tweet_details)
        self.client.add_view(view=view)
        await message.edit(view=view)

        await view.wait()
        await message.edit(view=None)

    
    async def on_connect(self):
        print("Stream connected")


    async def on_disconnect(self):
        print("Stream disconnected")

    
    async def on_data(self, raw_data):
        data = json.loads(raw_data)
        print("Data >>> ", data)

        # To run asynchronous tasks in a separate coroutine so that it doesn't block the main event loop
        loop = asyncio.get_event_loop()
        loop.create_task(self.send_post(data))



class FansiteFeed():
    def __init__(self):
        with open("src/cogs/cm_auto_post/IDs.txt") as data:
            lines = data.read().splitlines()
            user_ids = [user_id for user_id in lines]

        # self.follow = user_ids
        self.follow = ["1578046589578661888"]
        self.stream: FansiteStreamingClient = None
        self.task: asyncio.Task = None
        self.client: discord.Client = None

        self.rule_prefix = "(from:"
        self.rule_postfix = ") has:media"
        self.rule_connector = " OR from:"
        self.max_rule_content_length = 512 - (len(self.rule_prefix) + len(self.rule_postfix))

    
    def save_user_id(self, purpose: Literal["add", "remove"], user_id: str):
        with open("src/cogs/cm_auto_post/IDs.txt", "r+") as data:
            lines = data.read().splitlines()
            data.seek(0) # Moves the file pointer to the first index so it replaces the content

            if purpose == "remove":
                lines.remove(user_id)
            else:
                lines.append(user_id)
            
            data.write("\n".join(lines))
            data.truncate()
        

    def generate_rule_contents(self, user_id: str, user_ids: List[str], rule_content: str = "", rule_contents: List[str] = []):
        content = f"{user_id}" if rule_content == "" else f"{self.rule_connector}{user_id}"
        temp_rule_content = f"{rule_content}{content}"

        if len(user_ids) == 0:
            rule_contents.append(f"{self.rule_prefix}{temp_rule_content}{self.rule_postfix}")
            return rule_contents
        if len(temp_rule_content) >= self.max_rule_content_length:
            rule_contents.append(f"{self.rule_prefix}{rule_content}{self.rule_postfix}")
            return self.generate_rule_contents(user_id, user_ids, rule_contents=rule_contents)
        else:
            next_user_id = user_ids.pop(0)
            return self.generate_rule_contents(next_user_id, user_ids, temp_rule_content, rule_contents)


    def generate_stream_rules(self):
        user_ids = self.follow.copy()
        first_user_id = user_ids.pop(0)
        rule_contents = self.generate_rule_contents(first_user_id, user_ids)
        return [tweepy.StreamRule(rule_content) for rule_content in rule_contents]

    
    async def clear_stream_rules(self):
        current_rules = await self.stream.get_rules()
        if self.stream is not None and current_rules.data is not None:
            await self.stream.delete_rules([rule.id for rule in current_rules.data])


    async def start_stream(self, client: discord.Client):
        self.client = client

        # ! Can't setup more than 1 stream concurrently if there are more than a certain amount of user IDs
        self.stream = FansiteStreamingClient(client)

        await self.clear_stream_rules()
        await self.stream.add_rules(self.generate_stream_rules())

        self.task = self.stream.filter(
            tweet_fields=["attachments"], media_fields=['url'], user_fields=['name', 'username'], expansions=['attachments.media_keys', 'author_id']
        ) # Don't need await so it doesn't block the main loop execution

        print("Stream task: ", self.stream.task) # The task variable is to see which asyncio task is currently running

    
    async def close_stream(self):
        self.stream.disconnect() # Doesn't force a direct disconnection as it waits until the next cycle in the event loop to disconnect
        await self.stream.session.close() # Close the websocket connection to Twitter's API - this forces a direct disconnection


    async def restart_stream(self):
        if self.stream is not None and self.client is not None:
            await self.close_stream()
            await self.start_stream(self.client)
