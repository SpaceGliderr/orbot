import asyncio
from typing import List, Union

import discord

from src.cogs.content_poster.ui.embeds import PostDetailsEmbed, set_embed_author
from src.cogs.content_poster.ui.views.post_details import (
    PostMediaView,
    get_post_caption,
    send_post_caption_view,
)
from src.modules.ui.common import Button, View
from src.typings.content_poster import PostDetails
from src.utils.config import ContentPosterConfig
from src.utils.helper import dict_has_key
from src.utils.user_input import get_user_input, send_input_message


class EditPostView(View):
    """Creates a view to edit a Post by inheriting the `View` class.

    Additional Parameters
    ----------
        * post_details: :class:`PostDetails`
            - The post details to be edited.
        * embedded_message: Union[:class:`discord.Message`, :class:`discord.InteractionMessage`]
            - The message with the `PostDetailsEmbed`.
        * bot: :class:`discord.Client`
            - The Discord bot instance needed to wait for user input.
        * files: List[:class:`discord.File`]
            - A copied reference list to the original files found in the Posts' attachment attribute.
        * interaction_user: Union[:class:`discord.User`, :class:`discord.Member`]
            - The user that is allowed to interact with this `View`.
    """

    def __init__(
        self,
        post_details: PostDetails,
        embedded_message: Union[discord.Message, discord.InteractionMessage],
        bot: discord.Client,
        files: List[discord.File],
        interaction_user: Union[discord.User, discord.Member],
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        # Initialize arguments as instance variables
        self.post_details = post_details
        self.embedded_message = embedded_message
        self.bot = bot
        self.files = files
        self.interaction_user = interaction_user

        # Initialize other instance variables
        self.active_views: List[View] = []
        self.executing_tasks = None
        self.is_confirmed = False
        self.input_message: discord.Message = None

        # Initialize the buttons in the View
        self.button_rows = [
            {
                "buttons": [
                    {
                        "name": "edit_caption",
                        "label": "Edit Caption",
                        "style": discord.ButtonStyle.primary,
                        "emoji": None,
                        "callback": self.edit_caption,
                    },
                    {
                        "name": "add_images",
                        "label": "Add Image(s)",
                        "style": discord.ButtonStyle.primary,
                        "emoji": None,
                        "callback": self.add_images,
                    },
                    {
                        "name": "select_images",
                        "label": "Select Image(s)",
                        "style": discord.ButtonStyle.primary,
                        "emoji": None,
                        "callback": self.select_images,
                    },
                ],
            },
            {
                "buttons": [
                    {
                        "name": "save",
                        "label": "Save",
                        "style": discord.ButtonStyle.green,
                        "emoji": "✔️",
                        "callback": self.save,
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
        """Stops all active views created by interacting with `EditPostView` view."""
        for active_view in self.active_views:
            active_view.stop()

    async def clear_tasks_and_msg(self):
        """Cancels all `asyncio.Task`s and deletes all messages created by interacting with `EditPostView` view."""
        if self.input_message is not None:
            await self.input_message.delete()
            self.input_message = None

        if self.executing_tasks is not None:
            for task in self.executing_tasks:
                if not task.done():
                    task.cancel()

            self.executing_tasks = None

    # =================================================================================================================
    # BUTTON CALLBACKS
    # =================================================================================================================
    async def edit_caption(self, interaction: discord.Interaction, *_):
        """Callback attached to the `edit_caption` button which edits the post caption."""
        # No need to call `clear_tasks_and_msg` method after `stop_active_views`
        # By stopping the active views, the input messages created by the `add_images` button will be handled by its callback, if any
        await self.stop_active_views()

        # Get the `post_caption_view` object
        post_caption_interaction, post_caption_view = await send_post_caption_view(
            url=self.post_details["message"].jump_url,
            caption_credits=self.post_details["caption_credits"],
            bot=self.bot,
            interaction=interaction,
            embed_type="edit",
            default_caption=self.post_details["caption"] if dict_has_key(self.post_details, "caption") else None,
        )

        self.active_views.append(post_caption_view)

        # Sends the prompt to retrieve user input
        post_caption_details = await get_post_caption(
            interaction=post_caption_interaction, post_caption_view=post_caption_view
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

    async def add_images(self, interaction: discord.Interaction, *_):
        """Callback attached to the `add_images` button which takes user inputted files and adds them to the files to upload."""
        await self.stop_active_views()
        await self.clear_tasks_and_msg()  # Use `clear_tasks_and_msg` here to delete the input messages created by `edit_caption`, if any

        # Obtain the user input
        self.input_message, cancel_view = await send_input_message(
            bot=self.bot, input_name="new images", interaction=interaction
        )

        self.active_views.append(cancel_view)

        self.executing_tasks = [
            asyncio.create_task(
                self.bot.wait_for(
                    "message",
                    check=lambda message: message.author == interaction.user
                    and message.channel == self.input_message.channel,
                )
            ),
            asyncio.create_task(cancel_view.wait()),
        ]

        task_result = await get_user_input(self.executing_tasks)

        self.active_views.remove(cancel_view)

        # After user input is obtained
        if isinstance(task_result, discord.Message):
            # If user input is a message, extract the attachments and turn them into `discord.File` objects
            new_files = [await attachment.to_file() for attachment in task_result.attachments]

            # Replace the file related instance variables
            self.post_details["files"].extend(new_files)
            self.files.extend(new_files)

            # Clean up the frontend UI, leftover tasks, and update relevant messages with the updated `post_details` variable
            await asyncio.gather(
                self.clear_tasks_and_msg(),
                task_result.delete(),
                self.embedded_message.edit(
                    embed=set_embed_author(
                        interaction=interaction, embed=PostDetailsEmbed(post_details=self.post_details)
                    )
                ),
                interaction.followup.send(content="Changes were recorded", ephemeral=True),
            )
        elif isinstance(task_result, bool):
            # True means it timed out, False means it was cancelled by the user
            content = "The user input timed out, please try again!" if task_result else "No images were uploaded."
            await asyncio.gather(self.clear_tasks_and_msg(), interaction.followup.send(content=content, ephemeral=True))

    async def select_images(self, interaction: discord.Interaction, *_):
        """Callback attached to the `select_images` button which allows users to select the files to upload."""
        # Send `PostMediaView` view to user
        post_medias_view = PostMediaView(
            timeout=120, medias=self.files, stop_view=False, defer=True, defaults=self.post_details["files"]
        )

        await interaction.response.send_message(
            content="Please select the image(s) that you want to keep:", view=post_medias_view, ephemeral=True
        )
        self.active_views.append(post_medias_view)

        # After user is done interacting with `post_medias_view`
        timeout = await post_medias_view.wait()
        self.active_views.remove(post_medias_view)

        if timeout:
            await interaction.edit_original_response(content="The command has timed out, please try again!", view=None)
        elif post_medias_view.is_confirmed and len(post_medias_view.ret_val) != 0:
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
        else:  # Cancel button clicked or Confirm button clicked but no new images was selected
            await interaction.edit_original_response(content="No changes were made!", view=None)

    async def save(self, interaction: discord.Interaction, *_):
        """Callback attached to the `save` button which edits the original post with the updated details."""
        if len(self.post_details["files"]) == 0:  # Make sure the user selects at least 1 image to upload
            await interaction.response.send_message(content="Please upload at least one image", ephemeral=True)
            return

        # Clean up the frontend UI, leftover tasks, and edit the original post with the new post details
        await asyncio.gather(
            self.clear_tasks_and_msg(),
            self.stop_active_views(),
            interaction.response.send_message(content="Updating...", ephemeral=True),
            self.post_details["message"].edit(
                content=self.post_details["caption"], attachments=self.post_details["files"]
            ),
        )

        # Once original post is updated, a success message is sent
        await interaction.edit_original_response(
            content=f"The post was successfully edited in <#{self.post_details['message'].channel.id}>. {self.post_details['message'].jump_url}"
        )

        self.is_confirmed = True
        self.interaction = interaction
        self.stop()

    async def cancel(self, interaction: discord.Interaction, *_):
        """Callback attached to the `cancel` button which stops user interaction with the `View`."""
        await asyncio.gather(
            self.clear_tasks_and_msg(),
            self.stop_active_views(),
            interaction.response.send_message(content="Post not updated", ephemeral=True),
        )  # Clean up the frontend UI, leftover tasks and send cancellation message

        self.stop()
        self.interaction = interaction
