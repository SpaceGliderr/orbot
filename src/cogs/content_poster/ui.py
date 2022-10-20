import asyncio
from multiprocessing.connection import Client
from operator import itemgetter
from typing import Any, List, Literal, Optional, Tuple, TypedDict, Union

import discord

from src.utils.config import ContentPosterConfig
from src.utils.helper import dict_has_key
from src.utils.ui import Button, Modal, Select, View


# =================================================================================================================
# CONTENT POSTER TYPES
# =================================================================================================================
class TweetDetails(TypedDict):
    user: TypedDict("TwitterUser", {"id": str, "name": str, "username": str})
    url: str


class EditPostDetails(TypedDict):
    message: discord.Message
    caption: str
    caption_credits: Union[Tuple[str, str], None]
    files: List[discord.File]


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
        * post_details: Optional[:class:`dict`]
            - The post details to display in the embed. Possible keys: `event_details`, `caption`.
    """

    def __init__(
        self,
        embed_type: Literal["new", "edit"],
        caption_credits: Optional[Tuple[str, str]],
        post_details: Optional[dict] = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.title = f"{embed_type.capitalize()} Post Details"
        self.description = f"{embed_type.capitalize()} post details for Tweet"

        if caption_credits is not None:
            self.description += f"by @{caption_credits[1]}"

        caption = ContentPosterConfig.generate_post_caption(caption_credits, post_details)

        self.add_field(
            name="Event Details",
            value=f'{post_details["event_details"]}\n\u200B'
            if post_details is not None and dict_has_key(post_details, "event_details")
            else "-No event details entered-\n\u200B",
            inline=False,
        )
        self.add_field(
            name="Custom Caption",
            value=f'{post_details["caption"]}\n\u200B'
            if post_details is not None and dict_has_key(post_details, "caption")
            else "-No custom caption entered-\n\u200B",
            inline=False,
        )
        self.add_field(
            name="Caption Preview", value=caption if caption is not None else "-No preview generated-", inline=False
        )


class EditPostEmbed(discord.Embed):
    """Creates an embed that shows the Post details by inheriting the `discord.Embed` class. Only shown when editing a post.

    Additional Parameters
    ----------
        * post_details: :class:`EditPostDetails`
            - The post details to display in the embed.
    """

    def __init__(self, post_details: EditPostDetails, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.title = "Edit Post"
        self.description = f"Edits the post made in <#{post_details['message'].channel.id}> with a message ID of {post_details['message'].id}"

        self.add_field(name="Caption", value=post_details["caption"], inline=False)
        self.add_field(
            name="Files",
            value=", ".join([f.filename for f in post_details["files"]])
            if len(post_details["files"]) != 0
            else "-No files were uploaded-",
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
        del self.view.post_details[self.input_name]

        await self.view.embedded_message.edit(
            embed=PostCaptionEmbed(
                url=self.post_url,
                embed_type=self.embed_type,
                caption_credits=self.caption_credits,
                post_details=self.view.post_details,
            )
        )

        await interaction.response.defer()


class EditPostButton(discord.ui.Button):
    """Creates a clear button by inheriting the `discord.ui.Button` class.
    This button will clear any user input with the `input_name` from the `post_details` attribute in its parent view.

    Additional Parameters
    ----------
        * callback_type: Literal[`edit_caption`, `add_image`, `remove_image`, `save`, `stop`]
            - The input name the button associates with. Used to delete the respective key in the `post_details` attribute.
        * post_details: :class:`EditPostDetails`
            - The parameters needed to update the `PostCaptionEmbed` embed.
        * bot: :class:`discord.Client`
            - The parameters needed to update the `PostCaptionEmbed` embed.

    Additional Attributes
    ----------
        * is_cancelled: :class:`bool` = False
            - Whether the parent view is cancelled or not
    """

    def __init__(
        self,
        callback_type: Literal["edit_caption", "add_image", "remove_image", "save", "stop"],
        post_details: EditPostDetails,
        bot: discord.Client,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.callback_type = callback_type
        self.post_details = post_details
        self.bot = bot

        self.callbacks = {
            "edit_caption": self.edit_caption,
            "add_image": self.add_image,
            "remove_image": self.remove_image,
            "save": self.save,
            "stop": self.stop,
        }
        self.is_cancelled = False

    async def edit_caption(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            embed=PostCaptionEmbed(
                url=self.post_details["message"].jump_url,
                embed_type="edit",
                caption_credits=self.post_details["caption_credits"],
            )
        )
        embedded_message = await interaction.original_response()

        post_caption_view = PostCaptionView(
            embedded_message=embedded_message,
            timeout=90,
            post_url=self.post_details["message"].jump_url,
            embed_type="edit",
            caption_credits=self.post_details["caption_credits"],
            bot=self.bot,
        )
        await interaction.edit_original_response(view=post_caption_view)

        timeout = await post_caption_view.wait()

        await interaction.edit_original_response(view=None)

        if timeout:
            await interaction.followup.send(content="The command has timed out, please try again!", ephemeral=True)
        elif post_caption_view.is_confirmed:
            caption = ContentPosterConfig.generate_post_caption(
                self.post_details["caption_credits"], post_caption_view.post_details
            )
            self.view.post_details["caption"] = caption
            await self.view.embedded_message.edit(embed=EditPostEmbed(post_details=self.view.post_details))
            await embedded_message.delete()

    async def add_image(self, interaction: discord.Interaction):
        await interaction.response.defer()

        cp_conf = ContentPosterConfig()

        feed_channel = await interaction.guild.fetch_channel(cp_conf.data["config"]["feed_channel_id"])

        user_input_embed = discord.Embed(
            title=f"Enter the new images",
            description=f"The next message you send in <#{feed_channel.id}> will be recorded as the new images",
        )
        user_input_embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.avatar)
        user_input_embed.set_footer(
            text="Data is recorded successfully when the previous embed is updated with the data."
        )

        cancel_view = CancelView(timeout=30)
        message = await feed_channel.send(embed=user_input_embed, view=cancel_view)  # TODO: Do an embed

        self.input_message = message

        finished, unfinished = await asyncio.wait(
            [
                self.bot.wait_for(
                    "message",
                    check=lambda message: message.author == interaction.user and message.channel == feed_channel,
                ),
                cancel_view.wait(),
            ],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in unfinished:
            task.cancel()

        # TODO: Keep track of unfinished tasks and message sent, when the cancel button is clicked, delete all of that and remove the coroutines
        if self.is_cancelled:
            print("Cancelled effective")
            return

        if isinstance(list(finished)[0].result(), discord.Message):
            user_input = list(finished)[0].result()
            self.view.post_details["files"].extend(
                [await attachment.to_file() for attachment in user_input.attachments]
            )
            await user_input.delete()
            await message.delete()

            # TODO: Add Twitter link to the Embed
            await self.view.embedded_message.edit(embed=EditPostEmbed(post_details=self.view.post_details))
            return

        elif list(finished)[0].result():  # True signifies that it is timed out
            await interaction.followup.send(content=f"The user input timed out, please try again!", ephemeral=True)
        else:  # False signifies the cancel button was clicked
            await interaction.followup.send(content=f"The images was not entered", ephemeral=True)

        await message.delete()

    async def remove_image(self, interaction: discord.Interaction):
        remove_image_view = View()
        options = [
            discord.SelectOption(label=f"Image {idx + 1}", description=f.filename, value=idx, default=True)
            for idx, f in enumerate(self.view.post_details["files"])
        ]
        remove_image_view.add_item(
            Select(
                min_values=0,
                max_values=len(options),
                options=options,
                placeholder="Choose image(s) to remove",
                stop_view=True,
                name="keep_image_select",
                defer=True,
            )
        )

        await interaction.response.send_message(content="Please select the image(s) to keep", view=remove_image_view)
        await remove_image_view.wait()
        await interaction.delete_original_response()

        if dict_has_key(remove_image_view.ret_dict, "keep_image_select"):
            index_list = [int(idx) for idx in remove_image_view.ret_dict["keep_image_select"]]
            self.view.post_details["files"] = list(map(list(self.view.post_details["files"]).__getitem__, index_list))

            await self.view.embedded_message.edit(embed=EditPostEmbed(post_details=self.view.post_details))
            return

        await interaction.followup.send(content="No images were removed")

    async def save(self, interaction: discord.Interaction):

        # TODO: Edit original post
        if len(self.view.post_details["files"]) != 0:
            await interaction.response.defer()
            await self.view.post_details["message"].edit(
                content=self.view.post_details["caption"], attachments=self.view.post_details["files"]
            )
            self.view.is_confirmed = True
            self.view.interaction = interaction
            self.view.stop()
        else:
            await interaction.response.send_message(content="Please upload at least one image")

    async def stop(self, interaction: discord.Interaction):
        self.view.stop()
        self.view.interaction = interaction

    async def callback(self, interaction: discord.Interaction):
        await self.callbacks.get(self.callback_type, None)(interaction)
        self.view.interaction = interaction


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
        self.interaction = interaction
        self.stop()


class PostChannelAndDetailsView(View):
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
        images: Optional[List[discord.File]] = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.is_confirmed = False
        self.images = images

        if images is not None:
            options = [
                discord.SelectOption(label=f"Image {idx + 1}", description=image.filename, value=idx)
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

        cp_conf = ContentPosterConfig()

        if input_type == "button":
            for channel in cp_conf.post_channels:
                self.add_item(Button(label=channel["label"], value=channel["id"], stop_view=stop_view, defer=defer))
        else:
            options = cp_conf.generate_post_channel_options()
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
        # TODO: Add a check here to see whether user actually selected anything
        missing_fields = []
        if self.images is not None:
            if not dict_has_key(self.ret_dict, "post_channel_image_select"):
                missing_fields.append("image(s)")
            elif len(self.ret_dict["post_channel_image_select"]) == 0:
                missing_fields.append("image(s)")

        if not dict_has_key(self.ret_dict, "post_channel_select"):
            missing_fields.append("channel(s)")
        elif len(self.ret_dict["post_channel_select"]) == 0:
            missing_fields.append("channel(s)")

        if len(missing_fields) != 0:
            await interaction.response.send_message(
                content=f"Please select {' and '.join(missing_fields)} to create post", ephemeral=True
            )
            return

        self.is_confirmed = True
        self.interaction = interaction
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, custom_id="cancel", emoji="✖️", row=3)
    async def cancel(self, interaction: discord.Interaction, *_):
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
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.embedded_message = embedded_message
        self.input_names = {"event_details": "event details", "caption": "custom caption"}
        self.post_details = {}
        self.is_confirmed = False
        self.embed_type = embed_type
        self.bot = bot
        self.post_url = post_url
        self.caption_credits = caption_credits

        for idx, input_id in enumerate(self.input_names.keys()):
            self.add_item(
                ClearButton(
                    emoji="🗑",
                    row=idx,
                    post_url=self.post_url,
                    embed_type=self.embed_type,
                    caption_credits=self.caption_credits,
                    input_name=input_id,
                )
            )

        self.input_message = None
        self.is_cancelled = False

    async def retrieve_user_input(self, interaction: discord.Interaction, button_id: str):
        cp_conf = ContentPosterConfig()

        feed_channel = await interaction.guild.fetch_channel(cp_conf.data["config"]["feed_channel_id"])

        user_input_embed = discord.Embed(
            title=f"Enter the {self.input_names[button_id]}",
            description=f"The next message you send in <#{feed_channel.id}> will be recorded as the {self.input_names[button_id]}",
        )
        user_input_embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.avatar)
        user_input_embed.set_footer(
            text="Data is recorded successfully when the previous embed is updated with the data."
        )

        cancel_view = CancelView(timeout=30)
        message = await feed_channel.send(embed=user_input_embed, view=cancel_view)  # TODO: Do an embed

        self.input_message = message

        finished, unfinished = await asyncio.wait(
            [
                self.bot.wait_for(
                    "message",
                    check=lambda message: message.author == interaction.user and message.channel == feed_channel,
                ),
                cancel_view.wait(),
            ],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in unfinished:
            task.cancel()

        # TODO: Keep track of unfinished tasks and message sent, when the cancel button is clicked, delete all of that and remove the coroutines
        if self.is_cancelled:
            print("Cancelled effective")
            return

        # Set input message to none after message is deleted
        if isinstance(list(finished)[0].result(), discord.Message):
            user_input = list(finished)[0].result()
            self.post_details[button_id] = user_input.content
            await user_input.delete()
            await message.delete()
            self.input_message = None

            # TODO: Add Twitter link to the Embed
            await self.embedded_message.edit(
                embed=PostCaptionEmbed(
                    url=self.post_url,
                    embed_type=self.embed_type,
                    caption_credits=self.caption_credits,
                    post_details=self.post_details,
                )
            )
            return

        elif list(finished)[0].result():  # True signifies that it is timed out
            await cancel_view.interaction.response.send_message(
                content=f"The user input timed out, please try again!", ephemeral=True
            )
        else:  # False signifies the cancel button was clicked
            await cancel_view.interaction.response.send_message(
                content=f"The {self.input_names[button_id]} was not entered", ephemeral=True
            )

        await message.delete()
        self.input_message = None

    @discord.ui.button(
        label="Event Details", style=discord.ButtonStyle.primary, custom_id="event_details", emoji="📆", row=0
    )
    async def event_details(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.retrieve_user_input(interaction=interaction, button_id=button.custom_id)

    @discord.ui.button(
        label="Custom Caption", style=discord.ButtonStyle.primary, custom_id="caption", emoji="⚠️", row=1
    )
    async def custom(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.retrieve_user_input(interaction=interaction, button_id=button.custom_id)

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green, custom_id="confirm", emoji="✔️", row=2)
    async def post(self, interaction: discord.Interaction, *_):
        # TODO: Check whether caption is generated
        caption = ContentPosterConfig.generate_post_caption(self.caption_credits, self.post_details)

        if caption is None:
            await interaction.response.send_message(content="Please enter a caption before posting", ephemeral=True)
            return

        self.is_confirmed = True
        self.interaction = interaction
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, custom_id="cancel", emoji="✖️", row=2)
    async def cancel(self, interaction: discord.Interaction, *_):
        if self.input_message is not None:
            await self.input_message.delete()

        self.is_cancelled = True
        self.is_confirmed = False
        self.interaction = interaction
        self.stop()


class EditPostView(View):
    """Creates a view to add or edit a Post Caption by inheriting the `View` class.

    Additional Parameters
    ----------
        * post_details: :class:`EditPostDetails`
            - The post details to be edited.
        * embedded_message: Union[:class:`discord.Message`, :class:`discord.InteractionMessage`]
            - The message with the `EditPostEmbed`.
        * bot: :class:`discord.Client`
            - The Discord bot instance needed to wait for user input.
    """

    def __init__(
        self,
        post_details: EditPostDetails,
        embedded_message: Union[discord.Message, discord.InteractionMessage],
        bot: discord.Client,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.post_details = post_details
        self.embedded_message = embedded_message
        self.bot = bot

        self.is_confirmed = False
        self.buttons = [
            {"name": "edit_caption", "label": "Edit Caption", "style": discord.ButtonStyle.primary, "emoji": None},
            {"name": "add_image", "label": "Add Image(s)", "style": discord.ButtonStyle.primary, "emoji": None},
            {"name": "remove_image", "label": "Remove Image(s)", "style": discord.ButtonStyle.primary, "emoji": None},
            {"name": "save", "label": None, "style": discord.ButtonStyle.green, "emoji": "✔️"},
            {"name": "stop", "label": None, "style": discord.ButtonStyle.red, "emoji": "✖️"},
        ]

        for button in self.buttons:
            self.add_item(
                EditPostButton(
                    custom_id=f"persistent:{self.embedded_message.id}:{button['name']}",
                    label=button["label"],
                    style=button["style"],
                    emoji=button["emoji"],
                    callback_type=button["name"],
                    post_details=self.post_details,
                    bot=self.bot,
                )
            )


# =================================================================================================================
# CONTENT POSTER PERSISTENT ELEMENTS
# =================================================================================================================
class PersistentTweetButton(discord.ui.Button):
    """Creates a persistent Tweet button by inheriting the `discord.ui.Button` class.

    Additional Parameters
    ----------
        * callback_type: Literal[`select`, `all`, `stop`]
            - The callback that the button will use.
        * tweet_details: :class:`TweetDetails`
            - The Tweet details obtained from the Twitter stream.
        * files: List[:class:`discord.File`]
            - The downloaded files from the Tweets attached media.
        * bot: :class:`discord.Client`
            - An instance of the Discord bot.
    """

    def __init__(
        self,
        callback_type: Literal["select", "all", "stop"],
        tweet_details: TweetDetails,
        files: List[discord.File],
        bot: discord.Client,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.callback_type = callback_type
        self.tweet_details = tweet_details
        self.files = files
        self.bot = bot

        self.caption_credits = (self.tweet_details["user"]["name"], self.tweet_details["user"]["username"])
        self.callbacks = {"select": self.select, "all": self.all, "stop": self.stop}

    async def send_post_channel_view(
        self, interaction: discord.Interaction, images: Optional[List[discord.File]] = None
    ):
        post_details_view = PostChannelAndDetailsView(
            timeout=90, input_type="select", stop_view=False, defer=True, images=images
        )

        if images is not None:
            content = "Choose the image(s) that you want to post and channel(s) that you want to post the images in:"
        else:
            content = "Choose the channel(s) that you want to post in:"

        await interaction.response.send_message(content=content, view=post_details_view)
        timeout = await post_details_view.wait()
        await interaction.delete_original_response()

        if timeout:
            await interaction.followup.send(content="The command has timed out, please try again!", ephemeral=True)
        elif not post_details_view.is_confirmed:
            await interaction.followup.send(content="No post was sent", ephemeral=True)
        else:
            await self.send_post_view(post_details_view.interaction, post_details_view.ret_dict, images)

    async def send_post_view(self, interaction: discord.Interaction, values: dict, images: Optional[List[discord.File]] = None):
        post_channel_ids = values["post_channel_select"]
        images_to_post = (
            list(itemgetter(*list(map(int, values["post_channel_image_select"])))(self.files))
            if images is not None and self.callback_type == "select"
            else self.files
        )

        await interaction.response.send_message(
            embed=PostCaptionEmbed(
                url=self.tweet_details["url"], embed_type="new", caption_credits=self.caption_credits
            )
        )
        embedded_message = await interaction.original_response()
        post_caption_view = PostCaptionView(
            embedded_message=embedded_message,
            timeout=90,
            post_url=self.tweet_details["url"],
            embed_type="new",
            caption_credits=self.caption_credits,
            bot=self.bot,
        )
        await interaction.edit_original_response(view=post_caption_view)

        timeout = await post_caption_view.wait()

        await interaction.edit_original_response(view=None)

        if timeout:
            await interaction.followup.send(content="The command has timed out, please try again!", ephemeral=True)
        elif post_caption_view.is_confirmed:
            caption = ContentPosterConfig.generate_post_caption(self.caption_credits, post_caption_view.post_details)

            # The following for loop is to make it so that the Discord files are read from the first byte again after being sent as a message earlier
            # Being sent as a message initially means the byte-file pointer is at the end
            for image in images_to_post:
                image.fp.seek(0)

            post_channels = []
            for post_channel_id in post_channel_ids:
                post_channel = await interaction.guild.fetch_channel(int(post_channel_id))
                await post_channel.send(content=caption, files=images_to_post)
                post_channels.append(f"<#{post_channel.id}>")

            await interaction.followup.send(content=f"Post(s) successfully created in {', '.join(post_channels)}")

    async def select(self, interaction: discord.Interaction):
        await self.send_post_channel_view(interaction, self.files)

    async def all(self, interaction: discord.Interaction):
        await self.send_post_channel_view(interaction)

    async def stop(self, interaction: discord.Interaction):
        self.view.stop()
        self.view.interaction = interaction

    async def callback(self, interaction: discord.Interaction):
        await self.callbacks.get(self.callback_type, None)(interaction)


class PersistentTweetView(View):
    """Creates a persistent Tweet view by inheriting the `View` class.

    Has 3 buttons: (1) Send `PostChannelAndDetailsView`; (2) Send `PostCaptionView`; (3) Remove the `PersistentTweetView`

    Additional Parameters
    ----------
        * message_id: int
            - The ID of the message that the view is attached to. Used as an identifier to prefix the `custom_id` for each `PersistentTweetView`.
        * tweet_details: :class:`TweetDetails` || files: List[:class:`discord.File`] || bot: :class:`discord.Client`
            - The parameters needed to initialize the `PersistentTweetButton` button.
    """

    def __init__(
        self,
        message_id: int,
        files: List[discord.File],
        tweet_details: TweetDetails,
        bot: discord.Client,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.message_id = message_id
        self.tweet_details = tweet_details
        self.files = files
        self.bot = bot

        self.buttons = [
            {"name": "select", "label": "Select Images", "style": discord.ButtonStyle.primary, "emoji": None},
            {"name": "all", "label": "All Images", "style": discord.ButtonStyle.primary, "emoji": None},
            {"name": "stop", "label": None, "style": discord.ButtonStyle.red, "emoji": "✖️"},
        ]

        for button in self.buttons:
            self.add_item(
                PersistentTweetButton(
                    custom_id=f"persistent:{self.message_id}:{button['name']}",
                    label=button["label"],
                    style=button["style"],
                    callback_type=button["name"],
                    emoji=button["emoji"],
                    tweet_details=self.tweet_details,
                    files=self.files,
                    bot=self.bot,
                )
            )
