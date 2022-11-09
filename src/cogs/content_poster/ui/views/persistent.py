from typing import List

import discord

from src.cogs.content_poster.ui.embeds import PostDetailsEmbed, set_embed_author
from src.cogs.content_poster.ui.views.new_post import NewPostView
from src.modules.ui.common import Button, View
from src.typings.content_poster import PostDetails, TweetDetails
from src.utils.config import ContentPosterConfig


class PersistentTweetView(View):
    """Creates a view to create a Post by inheriting the `View` class.

    Additional Parameters
    ----------
        * message: :class:`discord.Message`
            - The message that the `PersistentTweetView` is attached to.
        * embedded_message: Union[:class:`discord.Message`, :class:`discord.InteractionMessage`]
            - The message with the `PostDetailsEmbed`.
        * tweet_details: :class:`TweetDetails`
            - Necessary details extrapolated from a Tweet object.
        * files: List[:class:`discord.File`]
            - A copied reference list to the original files found in the Posts' attachment attribute.
        * bot: :class:`discord.Client`
            - The Discord bot instance needed to wait for user input.
    """

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

        # Initialize arguments as instance variables
        self.message = message
        self.tweet_details = tweet_details
        self.files = files
        self.bot = bot

        # Initialize other instance variables
        self.embedded_message = None

        # Initialize the buttons in the View
        self.buttons = [
            {
                "name": "new_post",
                "label": "Make New Post",
                "style": discord.ButtonStyle.grey,
                "emoji": None,
                "callback": self.new_post,
            },
            {
                "name": "close_tweet",
                "label": None,
                "style": discord.ButtonStyle.red,
                "emoji": "✖️",
                "callback": self.close_tweet,
            },
        ]

        for button in self.buttons:
            self.add_item(
                Button(
                    custom_id=f"persistent:{self.message.id}:{button['name']}",
                    label=button["label"],
                    style=button["style"],
                    emoji=button["emoji"],
                    custom_callback=button["callback"],
                )
            )

        # Add this view as an active post in memory to be re-initialized as a persistent view when the bot restarts
        ContentPosterConfig().add_active_post(message_id=message.id, tweet_details=self.tweet_details)

    # =================================================================================================================
    # BUTTON CALLBACKS
    # =================================================================================================================
    async def new_post(self, interaction: discord.Interaction, *_):
        """Callback attached to the `new_post` button which sends a `PostDetailsEmbed` and a `NewPostView` to allow users to create a new post."""
        # Send user a `PostDetailsEmbed` to keep track of the entered information
        post_details = PostDetails(
            files=self.files,
            caption_credits=(self.tweet_details["user"]["name"], self.tweet_details["user"]["username"]),
            tweet_url=self.tweet_details["url"]
        )
        await interaction.response.send_message(
            embed=set_embed_author(interaction=interaction, embed=PostDetailsEmbed(post_details=post_details))
        )

        # Edit the previous message with a `NewPostView`
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
        """Callback attached to the `close_tweet` button which removes the view from the Tweet."""
        await self.message.edit(view=None)
        self.stop()
        self.interaction = interaction

        # Remove active post stored in memory as it doesn't need to be re-initialized anymore
        ContentPosterConfig().remove_active_post(message_id=self.message.id)
