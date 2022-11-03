import asyncio
from typing import List, Union

import discord

from src.cogs.content_poster.ui.embeds import PostDetailsEmbed, set_embed_author
from src.cogs.content_poster.ui.views.post_details import (
    PostMediaView,
    get_post_caption,
    send_post_caption_view,
)
from src.typings.content_poster import PostDetails
from src.utils.config import ContentPosterConfig
from src.utils.helper import dict_has_key
from src.modules.ui.common import Button, View
from src.utils.user_input import get_user_input, send_input_message


class EditPostView(View):
    """Creates a view to add or edit a Post Caption by inheriting the `View` class.

    Additional Parameters
    ----------
        * post_details: :class:`PostDetails`
            - The post details to be edited.
        * embedded_message: Union[:class:`discord.Message`, :class:`discord.InteractionMessage`]
            - The message with the `PostDetailsEmbed`.
        * bot: :class:`discord.Client`
            - The Discord bot instance needed to wait for user input.
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

        self.post_details = post_details
        self.embedded_message = embedded_message
        self.bot = bot
        self.files = files
        self.interaction_user = interaction_user

        self.is_confirmed = False
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
                        # check=lambda interaction: self.interaction_user == interaction.user,
                    )
                )

        self.active_views: List[View] = []
        self.input_message: discord.Message = None
        self.executing_tasks = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.interaction_user != interaction.user:
            await interaction.response.send_message(
                content="You are not allowed to interact with this post!", ephemeral=True
            )
        return self.interaction_user == interaction.user

    async def stop_active_views(self):
        for active_view in self.active_views:
            active_view.stop()

    async def clear_tasks_and_msg(self):
        if self.input_message is not None:
            await self.input_message.delete()
            self.input_message = None

        if self.executing_tasks is not None:
            for task in self.executing_tasks:
                if not task.done():
                    task.cancel()

            self.executing_tasks = None

    async def edit_caption(self, interaction: discord.Interaction, *_):
        await self.stop_active_views()
        # await self.clear_tasks_and_msg()

        post_caption_interaction, post_caption_view = await send_post_caption_view(
            url=self.post_details["message"].jump_url,
            caption_credits=self.post_details["caption_credits"],
            bot=self.bot,
            interaction=interaction,
            embed_type="edit",
            default_caption=self.post_details["caption"] if dict_has_key(self.post_details, "caption") else None,
        )

        self.active_views.append(post_caption_view)

        post_caption_details = await get_post_caption(
            interaction=post_caption_interaction, post_caption_view=post_caption_view
        )

        self.active_views.remove(post_caption_view)

        if post_caption_details is not None:
            caption = ContentPosterConfig.generate_post_caption(
                self.post_details["caption_credits"], post_caption_details
            )
            self.post_details["caption"] = caption

            await asyncio.gather(
                post_caption_interaction.edit_original_response(content="Changes were recorded", embed=None, view=None),
                self.embedded_message.edit(
                    embed=set_embed_author(
                        interaction=interaction, embed=PostDetailsEmbed(post_details=self.post_details)
                    )
                ),
            )

    async def add_images(self, interaction: discord.Interaction, *_):
        await self.stop_active_views()
        await self.clear_tasks_and_msg()

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

        if isinstance(task_result, discord.Message):
            new_files = [await attachment.to_file() for attachment in task_result.attachments]
            self.post_details["files"].extend(new_files)
            self.files.extend(new_files)

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
        elif isinstance(task_result, bool):  # True signifies that it is timed out
            content = "The user input timed out, please try again!" if task_result else "No images were uploaded."
            await self.clear_tasks_and_msg()
            await interaction.followup.send(content=content, ephemeral=True)

    async def select_images(self, interaction: discord.Interaction, *_):
        post_medias_view = PostMediaView(
            timeout=120, images=self.files, stop_view=False, defer=True, defaults=self.post_details["files"]
        )

        await interaction.response.send_message(
            content="Please select the image(s) that you want to keep:", view=post_medias_view, ephemeral=True
        )

        self.active_views.append(post_medias_view)
        timeout = await post_medias_view.wait()
        self.active_views.remove(post_medias_view)

        if timeout:
            await interaction.edit_original_response(content="The command has timed out, please try again!", view=None)
        elif not post_medias_view.is_confirmed:
            await interaction.edit_original_response(content="No changes were made!", view=None)
        elif len(post_medias_view.ret_val) != 0:
            index_list = [int(idx) for idx in post_medias_view.ret_val]
            self.post_details["files"] = list(map(list(self.files).__getitem__, index_list))

            await asyncio.gather(
                interaction.edit_original_response(content="Changes were recorded", view=None),
                self.embedded_message.edit(
                    embed=set_embed_author(
                        interaction=interaction, embed=PostDetailsEmbed(post_details=self.post_details)
                    )
                ),
            )
        else:
            await interaction.edit_original_response(content="No images were removed", view=None)

    async def save(self, interaction: discord.Interaction, *_):
        if len(self.post_details["files"]) == 0:
            await interaction.response.send_message(content="Please upload at least one image", ephemeral=True)
            return

        await asyncio.gather(
            self.clear_tasks_and_msg(),
            self.stop_active_views(),
            interaction.response.send_message(content="Updating...", ephemeral=True),
            self.post_details["message"].edit(
                content=self.post_details["caption"], attachments=self.post_details["files"]
            ),
        )
        await interaction.edit_original_response(
            content=f"The post was successfully edited in <#{self.post_details['message'].channel.id}>. {self.post_details['message'].jump_url}"
        )

        self.is_confirmed = True
        self.interaction = interaction
        self.stop()

    async def cancel(self, interaction: discord.Interaction, *_):
        await asyncio.gather(self.clear_tasks_and_msg(), self.stop_active_views(), interaction.response.defer())

        self.stop()
        self.interaction = interaction
