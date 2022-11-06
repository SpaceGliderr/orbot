import asyncio
from typing import List, Literal, Optional, Tuple, Union

import discord

from src.cogs.content_poster.ui.embeds import PostCaptionEmbed, set_embed_author
from src.modules.ui.common import Button, Select, View
from src.typings.content_poster import PostCaptionDetails
from src.utils.config import ContentPosterConfig
from src.utils.helper import dict_has_key
from src.utils.user_input import get_user_input, send_input_message


# =================================================================================================================
# POST CAPTION HELPER FUNCTIONS
# =================================================================================================================
async def send_post_caption_view(
    url: str,
    caption_credits: Tuple[str, str],
    bot: discord.Client,
    interaction: discord.Interaction,
    embed_type: Literal["new", "edit"],
    default_caption: Optional[str] = None,
):
    """Sends `PostCaptionEmbed` message and attaches `PostCaptionView` to the embedded message.

    Parameters
    ----------
        * url: :class:`str` || caption_credits: Tuple[:class:`str`, :class:`str`] || bot: :class:`discord.Client` || embed_type: Literal[`new`, `edit`]
            - The parameters needed to create the `PostCaptionEmbed` embed and `PostCaptionView` view.
        * interaction: :class:`discord.Interaction`
            - The interaction object used to send the message.
        * default_caption: Optional[:class:`str`] | None
            - The caption to take apart and obtain the default values for the caption.

    Returns
    ----------
        * Tuple[:class:`discord.Interaction`, :class:`PostCaptionView`]
    """
    # Extract the post caption details
    post_caption_details = (
        ContentPosterConfig.get_post_caption_content(default_caption)
        if default_caption is not None
        else {"has_credits": caption_credits is not None}
    )

    # Send message with `PostCaptionEmbed`
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
    embedded_message = await interaction.original_response()

    # Attach `PostCaptionView` to embedded message
    post_caption_view = PostCaptionView(
        embedded_message=embedded_message,
        timeout=120,
        post_url=url,
        embed_type=embed_type,
        caption_credits=caption_credits,
        bot=bot,
        post_caption_details=post_caption_details,
    )
    await interaction.edit_original_response(view=post_caption_view)

    return interaction, post_caption_view


async def get_post_caption(interaction: discord.Interaction, post_caption_view: View):
    """Handles the value returned from the user interaction with `PostCaptionView`.
    Sends appropriate messages based on the value returned from the `PostCaptionView` object.

    Parameters
    ----------
        * interaction: :class:`discord.Interaction`
            - The interaction object used to send the message.
        * post_caption_view: :class:`View`
            - The `PostCaptionView` object to handle.

    Returns
    ----------
        * :type:`PostCaptionDetails` | None
    """
    timeout = await post_caption_view.wait()
    await post_caption_view.clear_tasks_and_msg()

    if timeout:
        await interaction.edit_original_response(
            content="The command has timed out, please try again!", embed=None, view=None
        )
    elif post_caption_view.is_confirmed:
        return post_caption_view.post_caption_details
    else:
        await interaction.edit_original_response(content="No caption was entered!", embed=None, view=None)
    return None


# =================================================================================================================
# POST CAPTION VIEW
# =================================================================================================================
class PostCaptionView(View):
    """Creates a view to create or edit a Post Caption by inheriting the `View` class.

    Additional Parameters
    ----------
        * embedded_message: Union[:class:`discord.Message`, :class:`discord.InteractionMessage`]
            - The message with the `PostCaptionEmbed`.
        * post_url: :class:`str`
            -
        * bot: :class:`discord.Client`
            - The Discord bot instance needed to wait for user input.
        * post_caption_details: Optional[:class:`dict`]
            -
        * embed_type: Literal[`new`, `edit`] || caption_credits: Optional[Tuple[:class:`str`, :class:`str`]]
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

        # Initialize arguments as instance variables
        self.embedded_message = embedded_message
        self.post_url = post_url
        self.embed_type = embed_type
        self.caption_credits = caption_credits
        self.bot = bot
        self.post_caption_details = post_caption_details if post_caption_details is not None else {"has_credits": False}

        # Initialize other instance variables
        self.is_confirmed = False
        self.input_message: discord.Message = None
        self.executing_tasks = None

        # Initialize the buttons in the View
        self.add_item(
            Button(
                label="Caption Credits Unavailable"
                if caption_credits is None
                else "Disable Caption Credits"
                if self.post_caption_details["has_credits"]
                else "Enable Caption Credits",
                style=discord.ButtonStyle.green
                if self.post_caption_details["has_credits"]
                else discord.ButtonStyle.grey,
                emoji="⚠️" if caption_credits is None else "🅾️" if self.post_caption_details["has_credits"] else "❌",
                disabled=caption_credits is None,
                row=1,
                custom_callback=self.toggle_caption_credits,
            )
        )

    # =================================================================================================================
    # VIEW FUNCTIONS
    # =================================================================================================================
    async def clear_tasks_and_msg(self):
        """Cancels all `asyncio.Task`s and deletes all messages created by interacting with `PostCaptionView` view."""
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
    async def toggle_caption_credits(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Callback attached to the `toggle_caption_credits` button which appends or removes the author credits from the entered caption."""
        self.post_caption_details["has_credits"] = not self.post_caption_details["has_credits"]

        button.emoji = "🅾️" if self.post_caption_details["has_credits"] else "❌"
        button.label = (
            "Disable Caption Credits" if self.post_caption_details["has_credits"] else "Enable Caption Credits"
        )
        button.style = (
            discord.ButtonStyle.green if self.post_caption_details["has_credits"] else discord.ButtonStyle.grey
        )

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
                        post_caption_details=self.post_caption_details,
                    ),
                ),
                view=updated_view,
            ),
            interaction.response.defer(),
        )

    # =================================================================================================================
    # BUTTONS
    # =================================================================================================================
    @discord.ui.button(label="Enter Caption", style=discord.ButtonStyle.primary, emoji="📝", row=0)
    async def caption(self, interaction: discord.Interaction, *_):
        await asyncio.gather(interaction.response.defer(), self.clear_tasks_and_msg())

        # Obtain the user input
        self.input_message, cancel_view = await send_input_message(
            bot=self.bot, input_name="caption", interaction=interaction
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

        # After user input is obtained
        if isinstance(task_result, discord.Message):
            # If user input is a message, extract the message content into the `caption`
            self.post_caption_details["caption"] = task_result.content

            # Clean up the frontend UI, and update relevant messages with the updated `post_details` variable
            await asyncio.gather(
                task_result.delete(),
                self.embedded_message.edit(
                    embed=set_embed_author(
                        interaction=interaction,
                        embed=PostCaptionEmbed(
                            url=self.post_url,
                            embed_type=self.embed_type,
                            caption_credits=self.caption_credits,
                            post_caption_details=self.post_caption_details,
                        ),
                    )
                ),
            )
        elif isinstance(task_result, bool):
            # True means it timed out, False means it was cancelled by the user
            content = "The user input timed out, please try again!" if task_result else f"The caption was not entered."
            await interaction.followup.send(content=content, ephemeral=True)

    @discord.ui.button(style=discord.ButtonStyle.grey, emoji="🗑", row=0)
    async def clear_caption(self, interaction: discord.Interaction, *_):
        if dict_has_key(self.post_caption_details, "caption"):
            del self.post_caption_details["caption"]

        await asyncio.gather(
            self.embedded_message.edit(
                embed=set_embed_author(
                    interaction=interaction,
                    embed=PostCaptionEmbed(
                        url=self.post_url,
                        embed_type=self.embed_type,
                        caption_credits=self.caption_credits,
                        post_caption_details=self.view.post_details,
                    ),
                )
            ),
            interaction.response.defer(),
        )

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green, emoji="✔️", row=2)
    async def confirm(self, interaction: discord.Interaction, *_):
        caption = ContentPosterConfig.generate_post_caption(self.caption_credits, self.post_caption_details)
        if caption is None:
            await interaction.response.send_message(content="Please enter a caption before posting", ephemeral=True)
            return

        await asyncio.gather(interaction.response.defer(), self.clear_tasks_and_msg())
        self.is_confirmed = True
        self.interaction = interaction
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, emoji="✖️", row=2)
    async def cancel(self, interaction: discord.Interaction, *_):
        await asyncio.gather(interaction.response.defer(), self.clear_tasks_and_msg())

        self.is_confirmed = False
        self.interaction = interaction
        self.stop()


# =================================================================================================================
# POST CHANNEL VIEW
# =================================================================================================================
class PostChannelView(View):
    """Creates a view to select Post Channel(s) by inheriting the `View` class.

    Additional Parameters
    ----------
        * input_type: Literal[`button`, `select`] | `button`
            - Controls the input type of the view, either displays buttons or a select menu.
        * stop_view: :class:`bool` | False || defer: :class:`bool` | False
            - These parameters are passed into the `Select` and `Button` child components.
        * defaults: Optional[List[:class:`str`]] | None
            - The default selected channels. Only applies if the `input_type` is `select`.
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

        # Initialize instance variables
        self.input_type = input_type
        self.defaults = defaults
        self.is_confirmed = False
        self.buttons = [
            {
                "name": "confirm",
                "label": "Confirm",
                "style": discord.ButtonStyle.green,
                "emoji": "✔",
                "row": 1,
                "callback": self.confirm,
            },
            {
                "name": "cancel",
                "label": "Cancel",
                "style": discord.ButtonStyle.red,
                "emoji": "✖️",
                "row": 1,
                "callback": self.cancel,
            },
        ]

        # Initialize the item in the View depending on input type
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
                    stop_view=stop_view,
                    defer=defer,
                )
            )

            for button in self.buttons:
                self.add_item(
                    Button(
                        label=button["label"],
                        style=button["style"],
                        emoji=button["emoji"],
                        row=button["row"],
                        custom_callback=button["callback"],
                    )
                )

    # =================================================================================================================
    # BUTTON CALLBACKS
    # =================================================================================================================
    async def confirm(self, interaction: discord.Interaction, *_):
        """Callback attached to the `confirm` button which checks whether a channel has been selected and ends the user interaction."""
        if self.input_type == "select" and (
            (self.ret_val is None and self.defaults is None) or (self.ret_val is not None and len(self.ret_val == 0))
        ):  # User did not select anything
            await interaction.response.send_message(content="Please select media(s) to create post", ephemeral=True)
            return

        await interaction.response.defer()
        self.is_confirmed = self.ret_val is None
        self.interaction = interaction
        self.stop()

    async def cancel(self, interaction: discord.Interaction, *_):
        """Callback attached to the `cancel` button which stops user interaction with the `View`."""
        await interaction.response.defer()
        self.is_confirmed = False
        self.interaction = interaction
        self.stop()


# =================================================================================================================
# POST MEDIA VIEW
# =================================================================================================================
class PostMediaView(View):
    """Creates a view to select Post Channel(s) by inheriting the `View` class.

    Additional Parameters
    ----------
        * medias: List[:class:discord.File]
            - The list of medias to render in the dropdown menu.
        * stop_view: :class:`bool` | False || defer: :class:`bool` | False
            - These parameters are passed into the `Select` child components.
        * defaults: Optional[List[:class:`discord.File`]] | None
            - The default selected media.
    """

    def __init__(
        self,
        medias: List[discord.File],
        stop_view: bool = False,
        defer: bool = False,
        defaults: Optional[List[discord.File]] = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        # Initialize instance variables
        self.defaults = defaults
        self.is_confirmed = False

        # Initialize the dropdown in the View
        options = [
            discord.SelectOption(
                label=f"Image {idx + 1}",
                description=media.filename,
                value=idx,
                default=media in defaults if defaults is not None else None,
            )
            for idx, media in enumerate(medias)
        ]
        self.add_item(
            Select(
                options=options,
                placeholder="Choose media(s)",
                min_values=0,
                max_values=len(options),
                stop_view=stop_view,
                defer=defer,
            )
        )

    # =================================================================================================================
    # BUTTONS
    # =================================================================================================================
    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green, emoji="✔", row=1)
    async def confirm(self, interaction: discord.Interaction, *_):
        if (self.ret_val is None and self.defaults is None) or (
            self.ret_val is not None and len(self.ret_val == 0)
        ):  # User did not select anything
            await interaction.response.send_message(content="Please select media(s) to create post", ephemeral=True)
            return

        await interaction.response.defer()
        self.is_confirmed = self.ret_val is None  # Whether any new channels were selected
        self.interaction = interaction
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, emoji="✖️", row=1)
    async def cancel(self, interaction: discord.Interaction, *_):
        await interaction.response.defer()
        self.is_confirmed = False
        self.interaction = interaction
        self.stop()
