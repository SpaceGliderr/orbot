import asyncio
from operator import itemgetter
from typing import List, Union

import discord

from src.cogs.content_poster.ui.embeds import PostDetailsEmbed, set_embed_author
from src.cogs.content_poster.ui.views.post_details import (
    PostChannelView,
    PostMediaView,
    get_post_caption,
    send_post_caption_view,
)
from src.modules.ui.common import Button, View
from src.typings.content_poster import PostDetails, TweetDetails
from src.utils.config import ContentPosterConfig
from src.utils.helper import dict_has_key, get_from_dict


class ClearButton(discord.ui.Button):
    """Creates a clear button by inheriting the `discord.ui.Button` class.

    A custom clear button created for the `NewPostView` class to clear a specific set of fields from the view.

    Parameters
    ----------
        * fields: List[:class:`str`]
            - The list of fields to clear the user input from.
    """

    def __init__(
        self,
        fields: List[str],
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.fields = fields

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()

        for field in self.fields:
            if dict_has_key(self.view.post_details, field):
                if field == "files":
                    self.view.post_details[field] = []
                else:
                    del self.view.post_details[field]

        await self.view.embedded_message.edit(
            embed=set_embed_author(interaction=interaction, embed=PostDetailsEmbed(post_details=self.view.post_details))
        )


class NewPostView(View):
    """Creates a view to create a Post by inheriting the `View` class.

    Additional Parameters
    ----------
        * bot: :class:`discord.Client`
            - The Discord bot instance needed to wait for user input.
        * post_details: :class:`PostDetails`
            - The post details to be edited.
        * embedded_message: Union[:class:`discord.Message`, :class:`discord.InteractionMessage`]
            - The message with the `PostDetailsEmbed`.
        * tweet_details: :class:`TweetDetails`
            - Necessary details extrapolated from a Tweet object.
        * files: List[:class:`discord.File`]
            - A copied reference list to the original files found in the Posts' attachment attribute.
        * interaction_user: Union[:class:`discord.User`, :class:`discord.Member`]
            - The user that is allowed to interact with this `View`.
    """

    def __init__(
        self,
        bot: discord.Client,
        post_details: PostDetails,
        embedded_message: Union[discord.Message, discord.InteractionMessage],
        tweet_details: TweetDetails,
        files: List[discord.File],
        interaction_user: Union[discord.User, discord.Member],
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        # Initialize arguments as instance variables
        self.bot = bot
        self.post_details = post_details
        self.embedded_message = embedded_message
        self.tweet_details = tweet_details
        self.files = files
        self.interaction_user = interaction_user

        # Initialize other instance variables
        self.active_views: List[View] = []

        # Initialize the buttons in the View
        self.button_rows = [
            {
                "fields": ["caption"],
                "buttons": [
                    {
                        "name": "make_caption",
                        "label": "Make Caption",
                        "style": discord.ButtonStyle.primary,
                        "emoji": None,
                        "callback": self.make_caption,
                    }
                ],
            },
            {
                "fields": ["channels"],
                "buttons": [
                    {
                        "name": "select_channels",
                        "label": "Select Channels",
                        "style": discord.ButtonStyle.primary,
                        "emoji": None,
                        "callback": self.select_channels,
                    }
                ],
            },
            {
                "fields": ["files"],
                "buttons": [
                    {
                        "name": "select_images",
                        "label": "Select Images",
                        "style": discord.ButtonStyle.primary,
                        "emoji": None,
                        "callback": self.select_images,
                    }
                ],
            },
            {
                "fields": None,
                "buttons": [
                    {
                        "name": "post",
                        "label": "Post",
                        "style": discord.ButtonStyle.green,
                        "emoji": "📮",
                        "callback": self.post,
                    },
                    {
                        "name": "cancel",
                        "label": "Cancel",
                        "style": discord.ButtonStyle.red,
                        "emoji": "✖️",
                        "callback": self.cancel,
                    },
                ],
            },
        ]

        for idx, button_row in enumerate(self.button_rows):
            for button in button_row["buttons"]:
                self.add_item(
                    Button(
                        label=button["label"],
                        style=button["style"],
                        emoji=button["emoji"],
                        row=int(idx),
                        custom_callback=button["callback"],
                    )
                )

            if button_row["fields"] is not None:
                self.add_item(
                    ClearButton(
                        emoji="🗑",
                        row=int(idx),
                        fields=button_row["fields"],
                    )
                )

    # =================================================================================================================
    # VIEW FUNCTIONS
    # =================================================================================================================
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Overrides the `interaction_check` method for `discord.View`.
        Checks whether the user that interacts with this view is equal to the `interaction_user` instance variable.
        """
        if self.interaction_user != interaction.user:
            await interaction.response.send_message(
                content="You are not allowed to interact with this post!", ephemeral=True
            )
        return self.interaction_user == interaction.user

    async def stop_active_views(self):
        """Stops all active views created by interacting with `NewPostView` view."""
        for active_view in self.active_views:
            active_view.stop()

    async def create_new_post(self, interaction: discord.Interaction, post_channel_id: int):
        """Creates a new post in a given channel."""
        post_channel = await interaction.guild.fetch_channel(int(post_channel_id))

        # The following for loop is to make it so that the Discord files are read from the first byte again after being sent as a message earlier
        # Being sent as a message initially means the byte-file pointer is at the end
        files = []
        for media in self.post_details["files"]:
            with media.fp as media_binary:
                media_binary.seek(0)
                files.append(discord.File(media_binary, media.filename))

        await post_channel.send(content=get_from_dict(self.post_details, ["caption"]), files=self.post_details["files"])

    # =================================================================================================================
    # BUTTON CALLBACKS
    # =================================================================================================================
    async def make_caption(self, interaction: discord.Interaction, *_):
        """Callback attached to the `make_caption` button which allows users to select the channels to create the post in."""
        # Get the `post_caption_view` object
        post_caption_interaction, post_caption_view = await send_post_caption_view(
            url=self.tweet_details["url"],
            caption_credits=self.post_details["caption_credits"],
            bot=self.bot,
            interaction=interaction,
            embed_type="new",
            default_caption=self.post_details["caption"] if dict_has_key(self.post_details, "caption") else None,
        )

        self.active_views.append(post_caption_view)

        # Sends the prompt to retrieve user input
        post_caption_details = await get_post_caption(
            interaction=post_caption_interaction,
            post_caption_view=post_caption_view,
        )

        self.active_views.remove(
            post_caption_view
        )  # Remove `post_caption_view` from active views once interaction is done

        if post_caption_details is not None:
            # Update the `post_details` variable with newly obtained post caption
            caption = ContentPosterConfig.generate_post_caption(
                self.post_details["caption_credits"], post_caption_details
            )
            self.post_details["caption"] = caption

            # Update relevant messages with the updated `post_details` variable
            await asyncio.gather(
                post_caption_interaction.edit_original_response(content="Changes were recorded", embed=None, view=None),
                self.embedded_message.edit(
                    embed=set_embed_author(
                        interaction=interaction, embed=PostDetailsEmbed(post_details=self.post_details)
                    )
                ),
            )

    async def select_channels(self, interaction: discord.Interaction, *_):
        """Callback attached to the `select_channels` button which allows users to select the channels to create the post in."""
        # Send `PostChannelView` view to user
        post_channel_view = PostChannelView(
            timeout=120,
            input_type="select",
            stop_view=False,
            defer=True,
            defaults=self.post_details["channels"] if dict_has_key(self.post_details, "channels") else None,
        )

        await interaction.response.send_message(
            content="Choose the channel(s) that you want to post in:", view=post_channel_view, ephemeral=True
        )
        self.active_views.append(post_channel_view)

        # After user is done interacting with `post_channel_view`
        timeout = await post_channel_view.wait()
        self.active_views.remove(post_channel_view)

        if timeout:
            await interaction.edit_original_response(content="The command has timed out, please try again!", view=None)
        elif post_channel_view.is_confirmed and len(post_channel_view.ret_val) != 0:
            self.post_details["channels"] = post_channel_view.ret_val

            # Update relevant messages with the updated `post_details` variable
            await asyncio.gather(
                interaction.edit_original_response(content="Changes were recorded", view=None),
                self.embedded_message.edit(
                    embed=set_embed_author(
                        interaction=interaction, embed=PostDetailsEmbed(post_details=self.post_details)
                    )
                ),
            )
        else:  # Cancel button clicked or Confirm button clicked but no new images was selected
            await interaction.edit_original_response(content="No changes were made!", view=None)

    async def select_images(self, interaction: discord.Interaction, *_):
        """Callback attached to the `select_images` button which allows users to select the files to upload."""
        # Send `PostMediaView` view to user
        post_medias_view = PostMediaView(
            timeout=120, medias=self.files, stop_view=False, defer=True, defaults=self.post_details["files"]
        )

        await interaction.response.send_message(
            content="Choose the image(s) that you want to post:", view=post_medias_view, ephemeral=True
        )

        self.active_views.append(post_medias_view)

        # After user is done interacting with `post_medias_view`
        timeout = await post_medias_view.wait()
        self.active_views.remove(post_medias_view)

        if timeout:
            await interaction.edit_original_response(content="The command has timed out, please try again!", view=None)
        elif not post_medias_view.is_confirmed:
            await interaction.edit_original_response(content="No changes were made!", view=None)
        elif len(post_medias_view.ret_val) != 0:
            # The return array is the indexes of the images to keep from the `files` instance variable
            index_list = [int(idx) for idx in post_medias_view.ret_val]

            # Extracts the `discord.File` objects based on the array of indexes
            self.post_details["files"] = list(map(list(self.files).__getitem__, index_list))

            # Update relevant messages with the updated `post_details` variable
            await asyncio.gather(
                interaction.edit_original_response(content="Changes were recorded", view=None),
                self.embedded_message.edit(
                    embed=set_embed_author(
                        interaction=interaction, embed=PostDetailsEmbed(post_details=self.post_details)
                    )
                ),
            )
        else:  # Confirm button clicked but no new images was selected
            await interaction.edit_original_response(content="No images were removed", view=None)

    async def post(self, interaction: discord.Interaction, *_):
        """Callback attached to the `post` button which creates a post with the entered details."""
        # Ensure the following conditions are met before creating the post:
        #   1. There are files uploaded
        #   2. There are channel(s) selected
        if (len(self.post_details["files"]) == 0 or get_from_dict(self.post_details, ["channels"]) is None) or (
            get_from_dict(self.post_details, ["channels"]) is not None and len(self.post_details["channels"]) == 0
        ):
            await interaction.response.send_message(
                content="Failed to make post. Ensure that you have selected at least one post channel and file(s) to upload.",
                ephemeral=True,
            )
            return

        # Clean up the frontend UI, update relevant messages with the updated `post_details` variable and create new posts in selected channel(s)
        await asyncio.gather(
            self.embedded_message.edit(view=None),
            interaction.response.send_message(content="Sending...", ephemeral=True),
            self.stop_active_views(),
            *[
                self.create_new_post(interaction=interaction, post_channel_id=post_channel_id)
                for post_channel_id in self.post_details["channels"]
            ],
        )

        # Send success message after posts have been made
        await interaction.edit_original_response(
            content=f"Post(s) successfully created in <#{'>, <#'.join(self.post_details['channels'])}>"
        )

    async def cancel(self, interaction: discord.Interaction, *_):
        """Callback attached to the `cancel` button which stops user interaction with the `View`."""
        await asyncio.gather(
            self.embedded_message.delete(),
            self.stop_active_views(),
            interaction.response.send_message(content="Post not created", ephemeral=True),
        )  # Clean up the frontend UI, leftover tasks and send cancellation message
        self.stop()
        self.interaction = interaction
