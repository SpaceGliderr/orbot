import asyncio
from typing import List, Literal, Optional, Tuple, Union

import discord

from src.cogs.content_poster.ui.buttons import ClearButton
from src.cogs.content_poster.ui.embeds import (
    PostCaptionEmbed,
    set_embed_author,
)
from src.typings.content_poster import PostCaptionDetails
from src.utils.config import ContentPosterConfig
from src.utils.helper import dict_has_key
from src.modules.ui.common import Button, Select, View
from src.utils.user_input import get_user_input, send_input_message


async def send_post_caption_view(
    url,
    caption_credits,
    bot: discord.Client,
    interaction: discord.Interaction,
    embed_type,
    default_caption: Optional[str] = None,
):
    post_caption_details = (
        ContentPosterConfig.get_post_caption_content(default_caption)
        if default_caption is not None
        else {"has_credits": caption_credits is not None}
    )

    if not interaction.response.is_done():
        await interaction.response.send_message(
            embed=set_embed_author(
                interaction=interaction,
                embed=PostCaptionEmbed(
                    url=url,
                    embed_type=embed_type,
                    caption_credits=caption_credits,
                    post_caption_details=post_caption_details,
                ),
            ),
            ephemeral=True,
        )
    else:
        await interaction.followup.send(
            embed=set_embed_author(
                interaction=interaction,
                embed=PostCaptionEmbed(
                    url=url,
                    embed_type=embed_type,
                    caption_credits=caption_credits,
                    post_caption_details=post_caption_details,
                ),
            ),
            ephemeral=True,
        )
    post_caption_embed = await interaction.original_response()

    post_caption_view = PostCaptionView(
        embedded_message=post_caption_embed,
        timeout=120,
        post_url=url,
        embed_type=embed_type,
        caption_credits=caption_credits,
        bot=bot,
        post_caption_details=post_caption_details,
    )

    await interaction.edit_original_response(view=post_caption_view)

    return interaction, post_caption_view


async def get_post_caption(interaction: discord.Interaction, post_caption_view):
    timeout = await post_caption_view.wait()
    await post_caption_view.clear_tasks_and_msg()

    if timeout:
        await interaction.edit_original_response(
            content="The command has timed out, please try again!", embed=None, view=None
        )
    elif post_caption_view.is_confirmed:
        return post_caption_view.post_details
    else:
        await interaction.edit_original_response(content="No caption was entered!", embed=None, view=None)
    return None


class PostCaptionView(View):
    """Creates a view to add or edit a Post Caption by inheriting the `View` class.

    Additional Parameters
    ----------
        * embedded_message: Union[:class:`discord.Message`, :class:`discord.InteractionMessage`]
            - The message with the `PostCaptionEmbed`.
        * bot: :class:`discord.Client`
            - The Discord bot instance needed to wait for user input.
        * embed_type: Literal[`new`, `edit`] || caption_credits: Optional[Tuple[:class:`str`, :class:`str`]] || post_details: Optional[:class:`dict`]
            - The parameters needed to update the `PostCaptionEmbed` embed.
    """

    def __init__(
        self,
        embedded_message: Union[discord.Message, discord.InteractionMessage],
        post_url: str,
        embed_type: Literal["new", "edit"],
        caption_credits: Tuple[str, str],
        bot: discord.Client,
        post_caption_details: Optional[PostCaptionDetails] = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.embedded_message = embedded_message
        self.input_names = {"caption": "custom caption"}
        self.post_details = post_caption_details if post_caption_details is not None else {"has_credits": False}
        self.is_confirmed = False
        self.embed_type = embed_type
        self.bot = bot
        self.post_url = post_url
        self.caption_credits = caption_credits

        for idx, input_name in enumerate(self.input_names.keys()):
            self.add_item(
                ClearButton(
                    emoji="🗑",
                    row=idx,
                    post_url=self.post_url,
                    embed_type=self.embed_type,
                    caption_credits=self.caption_credits,
                    input_name=input_name,
                )
            )

        self.input_message: discord.Message = None
        self.executing_tasks = None

        self.add_item(
            Button(
                label="Caption Credits Unavailable"
                if caption_credits is None
                else "Disable Caption Credits"
                if self.post_details["has_credits"]
                else "Enable Caption Credits",
                style=discord.ButtonStyle.green if self.post_details["has_credits"] else discord.ButtonStyle.grey,
                emoji="⚠️" if caption_credits is None else "🅾️" if self.post_details["has_credits"] else "❌",
                disabled=caption_credits is None,
                row=1,
                custom_callback=self.toggle,
            )
        )

    async def clear_tasks_and_msg(self):
        if self.input_message is not None:
            await self.input_message.delete()
            self.input_message = None

        if self.executing_tasks is not None:
            for task in self.executing_tasks:
                if not task.done():
                    task.cancel()

            self.executing_tasks = None

    async def retrieve_user_input(self, interaction: discord.Interaction, button_id: str):
        self.input_message, cancel_view = await send_input_message(
            bot=self.bot, input_name=self.input_names[button_id], interaction=interaction
        )

        self.executing_tasks = [
            asyncio.create_task(
                self.bot.wait_for(
                    "message",
                    check=lambda message: message.author == interaction.user
                    and message.channel.id == self.input_message.channel.id,
                )
            ),
            asyncio.create_task(cancel_view.wait()),
        ]

        task_result = await get_user_input(self.executing_tasks, self.clear_tasks_and_msg)

        if isinstance(task_result, discord.Message):
            self.post_details[button_id] = task_result.content
            await asyncio.gather(
                task_result.delete(),
                self.embedded_message.edit(
                    embed=set_embed_author(
                        interaction=interaction,
                        embed=PostCaptionEmbed(
                            url=self.post_url,
                            embed_type=self.embed_type,
                            caption_credits=self.caption_credits,
                            post_caption_details=self.post_details,
                        ),
                    )
                ),
            )
        elif isinstance(task_result, bool):
            content = (
                "The user input timed out, please try again!"
                if task_result
                else f"The {self.input_names[button_id]} was not entered."
            )
            await interaction.followup.send(content=content, ephemeral=True)

    @discord.ui.button(label="Enter Caption", style=discord.ButtonStyle.primary, custom_id="caption", emoji="📝", row=0)
    async def custom(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.clear_tasks_and_msg()
        await self.retrieve_user_input(interaction=interaction, button_id=button.custom_id)

    async def toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.post_details["has_credits"] = not self.post_details["has_credits"]

        button.emoji = "🅾️" if self.post_details["has_credits"] else "❌"
        button.label = "Disable Caption Credits" if self.post_details["has_credits"] else "Enable Caption Credits"
        button.style = discord.ButtonStyle.green if self.post_details["has_credits"] else discord.ButtonStyle.grey

        self.remove_item(button)
        updated_view = self.add_item(button)

        await asyncio.gather(
            self.embedded_message.edit(
                embed=set_embed_author(
                    interaction=interaction,
                    embed=PostCaptionEmbed(
                        url=self.post_url,
                        embed_type=self.embed_type,
                        caption_credits=self.caption_credits,
                        post_caption_details=self.post_details,
                    ),
                ),
                view=updated_view,
            ),
            interaction.response.defer(),
        )

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green, emoji="✔️", row=2)
    async def confirm(self, interaction: discord.Interaction, *_):
        caption = ContentPosterConfig.generate_post_caption(self.caption_credits, self.post_details)
        if caption is None:
            await interaction.response.send_message(content="Please enter a caption before posting", ephemeral=True)
            return

        await interaction.response.defer()
        await self.clear_tasks_and_msg()
        self.is_confirmed = True
        self.interaction = interaction
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, emoji="✖️", row=2)
    async def cancel(self, interaction: discord.Interaction, *_):
        await interaction.response.defer()
        await self.clear_tasks_and_msg()

        self.is_confirmed = False
        self.interaction = interaction
        self.stop()


class PostChannelView(View):
    """Creates a view to select Post Channel(s) by inheriting the `View` class.

    Additional Parameters
    ----------
        * input_type: Literal[`button`, `select`] | `button`
            - Controls the input type of the view, either displays buttons or a select menu.
        * max_value_type: Literal[`single`, `multiple`] | `multiple`
            - Controls the number of maximum values for the select menu. The `multiple` option takes the total number of options as the maximum selectable values in the select menu.
        * images: Optional[List[:class:discord.File]]
            - Adds an additional image select menu.
        * stop_view: :class:`bool` | False || defer: :class:`bool` | False
            - These parameters are passed into the `Select` and `Button` child components.
    """

    def __init__(
        self,
        input_type: Literal["button", "select"] = "button",
        stop_view: bool = False,
        defer: bool = False,
        defaults: Optional[List[str]] = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.is_confirmed = False

        cp_conf = ContentPosterConfig()

        if input_type == "button":
            for channel in cp_conf.post_channels:
                self.add_item(Button(label=channel["label"], value=channel["id"], stop_view=stop_view, defer=defer))
        else:
            options = cp_conf.generate_post_channel_options(defaults=defaults)
            self.add_item(
                Select(
                    min_values=0,
                    max_values=len(options),
                    options=options,
                    placeholder="Choose post channel(s)",
                    row=2,
                    name="post_channel_select",
                    stop_view=stop_view,
                    defer=defer,
                )
            )

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green, custom_id="confirm", emoji="✔", row=3)
    async def confirm(self, interaction: discord.Interaction, *_):
        if not dict_has_key(self.ret_dict, "post_channel_select"):
            await interaction.response.send_message(content="Please select channel(s) to create post", ephemeral=True)
        elif len(self.ret_dict["post_channel_select"]) == 0:
            await interaction.response.send_message(content="Please select channel(s) to create post", ephemeral=True)

        await interaction.response.defer()

        self.is_confirmed = True
        self.interaction = interaction
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, custom_id="cancel", emoji="✖️", row=3)
    async def cancel(self, interaction: discord.Interaction, *_):
        await interaction.response.defer()
        self.is_confirmed = False
        self.interaction = interaction
        self.stop()


class PostMediaView(View):
    """Creates a view to select Post Channel(s) by inheriting the `View` class.

    Additional Parameters
    ----------
        * input_type: Literal[`button`, `select`] | `button`
            - Controls the input type of the view, either displays buttons or a select menu.
        * max_value_type: Literal[`single`, `multiple`] | `multiple`
            - Controls the number of maximum values for the select menu. The `multiple` option takes the total number of options as the maximum selectable values in the select menu.
        * images: Optional[List[:class:discord.File]]
            - Adds an additional image select menu.
        * stop_view: :class:`bool` | False || defer: :class:`bool` | False
            - These parameters are passed into the `Select` and `Button` child components.
    """

    def __init__(
        self,
        images: List[discord.File],
        stop_view: bool = False,
        defer: bool = False,
        defaults: Optional[List[discord.File]] = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.is_confirmed = False
        self.images = images

        options = [
            discord.SelectOption(
                label=f"Image {idx + 1}",
                description=image.filename,
                value=idx,
                default=image in defaults if defaults is not None else None,
            )
            for idx, image in enumerate(images)
        ]
        self.add_item(
            Select(
                options=options,
                placeholder="Choose image(s)",
                min_values=0,
                max_values=len(options),
                row=1,
                name="post_channel_image_select",
                stop_view=stop_view,
                defer=defer,
            )
        )

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green, emoji="✔", row=3)
    async def confirm(self, interaction: discord.Interaction, *_):
        # TODO: Add a check here to see whether user actually selected anything
        if self.ret_val is None:
            self.interaction = interaction
            self.stop()
            return

        if len(self.ret_val) == 0:
            await interaction.response.send_message(content="Please select image(s) to create post", ephemeral=True)
            return

        await interaction.response.defer()

        self.is_confirmed = True
        self.interaction = interaction
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, emoji="✖️", row=3)
    async def cancel(self, interaction: discord.Interaction, *_):
        await interaction.response.defer()
        self.is_confirmed = False
        self.interaction = interaction
        self.stop()
