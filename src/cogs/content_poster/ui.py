import asyncio
from operator import itemgetter
from typing import Awaitable, Callable, List, Literal, Optional, Tuple, TypedDict, Union

import discord
from typing_extensions import NotRequired

from src.utils.config import ContentPosterConfig
from src.utils.helper import dict_has_key, get_from_dict
from src.utils.ui import Button, Modal, Select, View


async def send_input_message(bot: discord.Client, input_name: str, interaction: discord.Interaction):
    cp_conf = ContentPosterConfig()
    feed_channel = cp_conf.get_feed_channel(bot)

    user_input_embed = discord.Embed(
        title=f"Enter {input_name}",
        description=f"The next message you send in <#{feed_channel.id}> will be recorded as the {input_name}",
    )
    user_input_embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.avatar)
    user_input_embed.set_footer(text="Data is recorded successfully when the previous embed is updated with the data.")

    cancel_view = CancelView(timeout=30)

    if not interaction.response.is_done():
        await interaction.response.send_message(embed=user_input_embed, view=cancel_view, ephemeral=True)
        message = await interaction.original_response()
    else:
        message = await interaction.followup.send(embed=user_input_embed, view=cancel_view, ephemeral=True, wait=True)
    return message, cancel_view


async def get_user_input(tasks: List[asyncio.Task], cleanup: Optional[Callable[[], Awaitable[None]]] = None):
    finished, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    result = list(finished)[0].result()
    if cleanup is not None:
        await cleanup()
    return result


async def send_post_caption_view(
    url,
    caption_credits,
    bot: discord.Client,
    interaction: discord.Interaction,
    embed_type,
    default_caption: Optional[str] = None,
):
    caption_content = (
        ContentPosterConfig.get_post_caption_content(default_caption) if default_caption is not None else None
    )

    post_caption_details = (
        {caption_content["type"]: caption_content["content"]} if caption_content is not None else None
    )

    if not interaction.response.is_done():
        await interaction.response.send_message(
            embed=PostCaptionEmbed(
                url=url,
                embed_type=embed_type,
                caption_credits=caption_credits,
                post_caption_details=post_caption_details,
            ),
            ephemeral=True,
        )
    else:
        await interaction.followup.send(
            embed=PostCaptionEmbed(
                url=url,
                embed_type=embed_type,
                caption_credits=caption_credits,
                post_caption_details=post_caption_details,
            ),
            ephemeral=True,
        )
    post_caption_embed = await interaction.original_response()

    post_caption_view = PostCaptionView(
        embedded_message=post_caption_embed,
        timeout=90,
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


# =================================================================================================================
# CONTENT POSTER TYPES
# =================================================================================================================
class TweetDetails(TypedDict):
    user: TypedDict("TwitterUser", {"id": str, "name": str, "username": str})
    url: str


class PostDetails(TypedDict):
    message: NotRequired[discord.Message | None]
    caption: NotRequired[str | None]
    caption_credits: NotRequired[Tuple[str, str] | None]
    channels: NotRequired[List[str] | None]
    files: List[discord.File]


class PostCaptionDetails(TypedDict, total=False):
    event_details: str
    caption: str
    default: str


# =================================================================================================================
# CONTENT POSTER MODALS
# =================================================================================================================
class PostChannelModal(Modal):
    """Creates a modal popup window to add or edit a Post Channel by inheriting the `Modal` class.

    Has 2 text inputs for `id` and `label`.

    Additional Parameters
    ----------
        * defaults: Optional[:class:`dict`]
            - Fills the default values for each text input. Possible keys: `id`, `label`.
    """

    def __init__(self, defaults: Optional[dict] = None, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.add_item(
            discord.ui.TextInput(
                label="Channel ID",
                placeholder="Enter channel ID",
                custom_id="id",
                default=defaults["id"] if defaults is not None else None,
            )
        )

        self.add_item(
            discord.ui.TextInput(
                label="Channel Label",
                placeholder="Enter channel label (defaults to channel name)",
                custom_id="label",
                default=defaults["label"] if defaults is not None else None,
            )
        )


# =================================================================================================================
# CONTENT POSTER EMBEDS
# =================================================================================================================
class PostCaptionEmbed(discord.Embed):
    """Creates an embed that shows the Post Caption details by inheriting the `discord.Embed` class.

    Additional Parameters
    ----------
        * embed_type: Literal[`new`, `edit`]
            - Determines the verb of the embeds `title` and `description`.
        * caption_credits: Optional[Tuple[:class:`str`, :class:`str`]]
            - The anatomized caption credits. The first element is the Twitter name, the second element is the Twitter handle.
        * post_caption_details: Optional[:class:`dict`]
            - The post details to display in the embed. Possible keys: `event_details`, `caption`.
    """

    def __init__(
        self,
        embed_type: Literal["new", "edit"],
        caption_credits: Optional[Tuple[str, str]],
        post_caption_details: Optional[dict] = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.title = f"{embed_type.capitalize()} Post Caption"
        self.description = f"{embed_type.capitalize()} post caption"

        if caption_credits is not None:
            self.description += f" by @{caption_credits[1]}"

        self.description += "\n\u200B"

        caption = ContentPosterConfig.generate_post_caption(caption_credits, post_caption_details)

        self.add_field(
            name="Event Details",
            value=f'{post_caption_details["event_details"]}\n\u200B'
            if post_caption_details is not None and dict_has_key(post_caption_details, "event_details")
            else "_-No event details entered-_\n\u200B",
            inline=False,
        )
        self.add_field(
            name="Custom Caption",
            value=f'{post_caption_details["caption"]}\n\u200B'
            if post_caption_details is not None and dict_has_key(post_caption_details, "caption")
            else "_-No custom caption entered-_\n\u200B",
            inline=False,
        )
        self.add_field(
            name="Caption Preview", value=caption if caption is not None else "_-No preview generated-_", inline=False
        )


class PostDetailsEmbed(discord.Embed):
    """Creates an embed that shows the Post details by inheriting the `discord.Embed` class. Only shown when editing a post.

    Additional Parameters
    ----------
        * post_details: :class:`PostDetails`
            - The post details to display in the embed.
    """

    def __init__(self, post_details: PostDetails, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if dict_has_key(post_details, "message"):
            self.title = "Edit Post"
            self.description = f"Edits the post made in <#{post_details['message'].channel.id}> with a message ID of {post_details['message'].id}\n\u200B"
        else:
            self.title = "New Post"
            self.description = "Enter details to make a new post\n\u200B"

        self.add_field(
            name="Caption",
            value=f'{post_details["caption"]}\u200B'
            if dict_has_key(post_details, "caption")
            else "_-No caption entered-_\n\u200B",
            inline=False,
        )
        self.add_field(
            name="Channel(s)",
            value=f"<#{'>, <#'.join(post_details['channels'])}>\n\u200B"
            if dict_has_key(post_details, "channels")
            else "_-No channel(s) selected-_\n\u200B",
            inline=False,
        )
        self.add_field(
            name="Media to upload (all uploaded by default)",
            value=", ".join([f.filename for f in post_details["files"]])
            if len(post_details["files"]) != 0
            else "_-No media(s) selected-_",
            inline=False,
        )


# =================================================================================================================
# CONTENT POSTER BUTTONS
# =================================================================================================================
class ClearButton(discord.ui.Button):
    """Creates a clear button by inheriting the `discord.ui.Button` class.
    This button will clear any user input with the `input_name` from the `post_details` attribute in its parent view.

    Additional Parameters
    ----------
        * input_name: :class:`str`
            - The input name the button associates with. Used to delete the respective key in the `post_details` attribute.
        * post_url: :class:`str` || embed_type: Literal[`new`, `edit`] || caption_credits: Tuple[:class:`str`, :class:`str`]
            - The parameters needed to update the `PostCaptionEmbed` embed.
    """

    def __init__(
        self,
        post_url: str,
        embed_type: Literal["new", "edit"],
        caption_credits: Tuple[str, str],
        input_name: str,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.post_url = post_url
        self.embed_type = embed_type
        self.caption_credits = caption_credits
        self.input_name = input_name

    async def callback(self, interaction: discord.Interaction):
        if dict_has_key(self.view.post_details, self.input_name):
            del self.view.post_details[self.input_name]

        await self.view.embedded_message.edit(
            embed=PostCaptionEmbed(
                url=self.post_url,
                embed_type=self.embed_type,
                caption_credits=self.caption_credits,
                post_caption_details=self.view.post_details,
            )
        )

        await interaction.response.defer()


# =================================================================================================================
# CONTENT POSTER VIEWS
# =================================================================================================================
class CancelView(View):
    """Creates a view with a cancel button by inheriting the `View` class."""

    def __init__(self, *, timeout: Optional[float] = None):
        super().__init__(timeout=timeout)
        self.interaction = None

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, emoji="✖️")
    async def cancel(self, interaction: discord.Interaction, *_):
        await interaction.response.defer()
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
        post_caption_details: Optional[dict] = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.embedded_message = embedded_message
        self.input_names = {"event_details": "event details", "caption": "custom caption"}
        self.post_details = post_caption_details if post_caption_details is not None else {}
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
                    embed=PostCaptionEmbed(
                        url=self.post_url,
                        embed_type=self.embed_type,
                        caption_credits=self.caption_credits,
                        post_caption_details=self.post_details,
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

    @discord.ui.button(
        label="Event Details", style=discord.ButtonStyle.primary, custom_id="event_details", emoji="📆", row=0
    )
    async def event_details(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.clear_tasks_and_msg()
        await self.retrieve_user_input(interaction=interaction, button_id=button.custom_id)

    @discord.ui.button(
        label="Custom Caption", style=discord.ButtonStyle.primary, custom_id="caption", emoji="⚠️", row=1
    )
    async def custom(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.clear_tasks_and_msg()
        await self.retrieve_user_input(interaction=interaction, button_id=button.custom_id)

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green, custom_id="confirm", emoji="✔️", row=2)
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

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, custom_id="cancel", emoji="✖️", row=2)
    async def cancel(self, interaction: discord.Interaction, *_):
        await interaction.response.defer()
        await self.clear_tasks_and_msg()

        self.is_confirmed = False
        self.interaction = interaction
        self.stop()


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
                        "name": "add_image",
                        "label": "Add Image(s)",
                        "style": discord.ButtonStyle.primary,
                        "emoji": None,
                        "callback": self.add_image,
                    },
                    {
                        "name": "remove_image",
                        "label": "Remove Image(s)",
                        "style": discord.ButtonStyle.primary,
                        "emoji": None,
                        "callback": self.remove_image,
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

    async def edit_caption(self, interaction: discord.Interaction):
        await self.stop_active_views()
        await self.clear_tasks_and_msg()

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
                self.embedded_message.edit(embed=PostDetailsEmbed(post_details=self.post_details)),
            )

    async def add_image(self, interaction: discord.Interaction):
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
                task_result.delete(),
                self.embedded_message.edit(embed=PostDetailsEmbed(post_details=self.post_details)),
                interaction.followup.send(content="Changes were recorded", ephemeral=True),
            )
        elif isinstance(task_result, bool):  # True signifies that it is timed out
            content = "The user input timed out, please try again!" if task_result else "No images were uploaded."
            await interaction.followup.send(content=content, ephemeral=True)

    async def remove_image(self, interaction: discord.Interaction):
        post_medias_view = PostMediaView(
            timeout=90, images=self.files, stop_view=False, defer=True, defaults=self.post_details["files"]
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
                self.embedded_message.edit(embed=PostDetailsEmbed(post_details=self.post_details)),
            )
        else:
            await interaction.edit_original_response(content="No images were removed", view=None)

    async def save(self, interaction: discord.Interaction):
        if len(self.post_details["files"]) == 0:
            await interaction.response.send_message(content="Please upload at least one image", ephemeral=True)
            return

        await asyncio.gather(
            self.clear_tasks_and_msg(),
            self.stop_active_views(),
            interaction.response.send_message(content="Sending...", ephemeral=True),
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

    async def cancel(self, interaction: discord.Interaction):
        await asyncio.gather(self.clear_tasks_and_msg(), self.stop_active_views(), interaction.response.defer())

        self.stop()
        self.interaction = interaction


class NewClearButton(discord.ui.Button):
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

        await self.view.embedded_message.edit(embed=PostDetailsEmbed(self.view.post_details))


class NewPostView(View):
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
        self.bot = bot
        self.post_details = post_details
        self.embedded_message = embedded_message
        self.tweet_details = tweet_details
        self.files = files
        self.interaction_user = interaction_user

        self.button_rows = [
            {
                "fields": ["caption"],
                "buttons": [
                    {
                        "name": "caption",
                        "label": "Enter Caption",
                        "style": discord.ButtonStyle.primary,
                        "emoji": None,
                        "callback": self.caption,
                    }
                ],
            },
            {
                "fields": ["channels"],
                "buttons": [
                    {
                        "name": "channel",
                        "label": "Select Channels",
                        "style": discord.ButtonStyle.primary,
                        "emoji": None,
                        "callback": self.channel,
                    }
                ],
            },
            {
                "fields": ["files"],
                "buttons": [
                    {
                        "name": "select",
                        "label": "Select Images",
                        "style": discord.ButtonStyle.primary,
                        "emoji": None,
                        "callback": self.select,
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
                    NewClearButton(
                        emoji="🗑",
                        row=int(idx),
                        fields=button_row["fields"],
                    )
                )

        self.active_views: List[View] = []

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.interaction_user != interaction.user:
            await interaction.response.send_message(
                content="You are not allowed to interact with this post!", ephemeral=True
            )
        return self.interaction_user == interaction.user

    async def stop_active_views(self):
        for active_view in self.active_views:
            active_view.stop()

    async def caption(self, interaction: discord.Interaction):
        post_caption_interaction, post_caption_view = await send_post_caption_view(
            url=self.tweet_details["url"],
            caption_credits=self.post_details["caption_credits"],
            bot=self.bot,
            interaction=interaction,
            embed_type="new",
            default_caption=self.post_details["caption"] if dict_has_key(self.post_details, "caption") else None,
        )

        self.active_views.append(post_caption_view)

        post_caption_details = await get_post_caption(
            interaction=post_caption_interaction,
            post_caption_view=post_caption_view,
        )

        self.active_views.remove(post_caption_view)

        if post_caption_details is not None:
            caption = ContentPosterConfig.generate_post_caption(
                self.post_details["caption_credits"], post_caption_details
            )
            self.post_details["caption"] = caption
            await post_caption_interaction.edit_original_response(
                content="Changes were recorded", embed=None, view=None
            )
            await self.embedded_message.edit(embed=PostDetailsEmbed(post_details=self.post_details))

    async def channel(self, interaction: discord.Interaction):
        post_details_view = PostChannelView(
            timeout=90,
            input_type="select",
            stop_view=False,
            defer=True,
            defaults=self.post_details["channels"] if dict_has_key(self.post_details, "channels") else None,
        )

        await interaction.response.send_message(
            content="Choose the channel(s) that you want to post in:", view=post_details_view, ephemeral=True
        )
        self.active_views.append(post_details_view)
        timeout = await post_details_view.wait()
        self.active_views.remove(post_details_view)

        if timeout:
            await interaction.edit_original_response(content="The command has timed out, please try again!", view=None)
        elif not post_details_view.is_confirmed:
            await interaction.edit_original_response(content="No post channels were selected!", view=None)
        else:
            self.post_details["channels"] = post_details_view.ret_val
            await asyncio.gather(
                interaction.edit_original_response(content="Changes were recorded", view=None),
                self.embedded_message.edit(embed=PostDetailsEmbed(post_details=self.post_details)),
            )

    async def select(self, interaction: discord.Interaction):
        post_medias_view = PostMediaView(
            timeout=90, images=self.files, stop_view=False, defer=True, defaults=self.post_details["files"]
        )

        await interaction.response.send_message(
            content="Choose the image(s) that you want to post:", view=post_medias_view, ephemeral=True
        )

        self.active_views.append(post_medias_view)
        timeout = await post_medias_view.wait()
        self.active_views.remove(post_medias_view)

        if timeout:
            await interaction.edit_original_response(content="The command has timed out, please try again!", view=None)
        elif not post_medias_view.is_confirmed:
            await interaction.edit_original_response(content="No changes were made!", view=None)
        else:
            values = post_medias_view.ret_val

            if len(values) == 1:
                self.post_details["files"] = [self.files[int(values[0])]]
            else:
                self.post_details["files"] = list(itemgetter(*list(map(int, values)))(self.files))

            await asyncio.gather(
                interaction.edit_original_response(content="Changes were recorded", view=None),
                self.embedded_message.edit(embed=PostDetailsEmbed(post_details=self.post_details)),
            )

    async def post(self, interaction: discord.Interaction):
        if (
            get_from_dict(self.post_details, ["caption"]) is None or
            len(self.post_details["files"]) == 0
        ):
            if get_from_dict(self.post_details, ["channels"]) is not None:
                if len(self.post_details["channels"]) != 0:
                    return
                
            await interaction.response.send_message(
                content="Failed to make post. Ensure that you have entered a caption and selected the channels to post in and files to upload.",
                ephemeral=True,
            )
            return

        await asyncio.gather(
            self.embedded_message.edit(view=None),
            interaction.response.send_message(content="Sending...", ephemeral=True),
            self.stop_active_views(),
        )

        for post_channel_id in self.post_details["channels"]:
            post_channel = await interaction.guild.fetch_channel(int(post_channel_id))

            # The following for loop is to make it so that the Discord files are read from the first byte again after being sent as a message earlier
            # Being sent as a message initially means the byte-file pointer is at the end
            files = []
            for media in self.post_details["files"]:
                with media.fp as media_binary:
                    media_binary.seek(0)
                    files.append(discord.File(media_binary, media.filename))

            await post_channel.send(content=self.post_details["caption"], files=self.post_details["files"])

        await interaction.edit_original_response(
            content=f"Post(s) successfully created in <#{'>, <#'.join(self.post_details['channels'])}>"
        )

    async def cancel(self, interaction: discord.Interaction):
        await self.embedded_message.delete()
        await self.stop_active_views()
        self.stop()
        self.interaction = interaction


# =================================================================================================================
# CONTENT POSTER PERSISTENT ELEMENTS
# =================================================================================================================
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

        self.post_details = PostDetails(
            files=self.files,
            caption_credits=(self.tweet_details["user"]["name"], self.tweet_details["user"]["username"]),
        )
        self.embedded_message = None

    async def new_post(self, interaction: discord.Interaction):
        post_details_embed = PostDetailsEmbed(post_details=self.post_details)
        post_details_embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.avatar)
        await interaction.response.send_message(embed=post_details_embed)
        self.embedded_message = await interaction.original_response()
        new_post_view = NewPostView(
            bot=self.bot,
            post_details=self.post_details,
            embedded_message=self.embedded_message,
            tweet_details=self.tweet_details,
            files=self.files,
            interaction_user=interaction.user,
            timeout=180,
        )
        await interaction.edit_original_response(view=new_post_view)
        await new_post_view.wait()

    async def close_tweet(self, interaction: discord.Interaction):
        await self.message.edit(view=None)
        self.stop()
        self.interaction = interaction
