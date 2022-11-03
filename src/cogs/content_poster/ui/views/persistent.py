from typing import List

import discord

from src.cogs.content_poster.ui.embeds import (
    PostDetailsEmbed,
    set_embed_author,
)
from src.cogs.content_poster.ui.views.new_post import NewPostView
from src.typings.content_poster import TweetDetails
from src.utils.config import ContentPosterConfig
from src.modules.ui.common import Button, View


class PersistentTweetView(View):
    def __init__(
        self,
        message: discord.Message,
        files: List[discord.File],
        tweet_details: TweetDetails,
        bot: discord.Client,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.message = message
        self.tweet_details = tweet_details
        self.files = files
        self.bot = bot

        self.buttons = [
            {"name": "new_post", "label": "Make New Post", "style": discord.ButtonStyle.grey, "emoji": None},
            {"name": "close_tweet", "label": None, "style": discord.ButtonStyle.red, "emoji": "✖️"},
        ]
        self.callbacks = {"new_post": self.new_post, "close_tweet": self.close_tweet}

        for button in self.buttons:
            self.add_item(
                Button(
                    custom_id=f"persistent:{self.message.id}:{button['name']}",
                    label=button["label"],
                    style=button["style"],
                    emoji=button["emoji"],
                    custom_callback=self.callbacks.get(button["name"], None),
                )
            )

        self.embedded_message = None

        ContentPosterConfig().add_active_post(message_id=message.id, tweet_details=self.tweet_details)

    async def new_post(self, interaction: discord.Interaction, *_):
        post_details = PostDetailsEmbed(
            files=self.files,
            caption_credits=(self.tweet_details["user"]["name"], self.tweet_details["user"]["username"]),
        )
        await interaction.response.send_message(
            embed=set_embed_author(interaction=interaction, embed=PostDetailsEmbed(post_details=post_details))
        )
        self.embedded_message = await interaction.original_response()
        new_post_view = NewPostView(
            bot=self.bot,
            post_details=post_details,
            embedded_message=self.embedded_message,
            tweet_details=self.tweet_details,
            files=self.files,
            interaction_user=interaction.user,
            timeout=300,
        )
        await interaction.edit_original_response(view=new_post_view)
        await new_post_view.wait()

    async def close_tweet(self, interaction: discord.Interaction, *_):
        await self.message.edit(view=None)
        self.stop()
        self.interaction = interaction

        ContentPosterConfig().remove_active_post(message_id=self.message.id)
