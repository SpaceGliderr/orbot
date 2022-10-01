import asyncio
from typing import Any, List, Literal, Optional, Union
from src.utils.ui import Button, Modal, Select, View

import discord

from src.utils.helper import dict_has_key
from src.utils.config import CMAutoPostConfig


class PostChannelModal(Modal):
    def __init__(
        self,
        *,
        title: str,
        timeout: Optional[float] = None,
        custom_id: Optional[str] = None,
        success_msg: Optional[str] = None,
        error_msg: Optional[str] = None,
        defaults: Optional[dict] = None,
        checks: Optional[List[dict]] = None,
    ) -> None:
        super().__init__(
            title=title,
            timeout=timeout,
            custom_id=custom_id,
            success_msg=success_msg,
            error_msg=error_msg,
            checks=checks,
        )

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


class PostModal(Modal):
    def __init__(
        self,
        *,
        title: str,
        timeout: Optional[float] = None,
        custom_id: Optional[str] = None,
        success_msg: Optional[str] = None,
        error_msg: Optional[str] = None,
        defaults: Optional[dict] = None,
        checks: Optional[List[dict]] = None,
    ) -> None:
        super().__init__(
            title=title,
            timeout=timeout,
            custom_id=custom_id,
            success_msg=success_msg,
            error_msg=error_msg,
            checks=checks,
        )
    
        self.add_item(
            discord.ui.TextInput(
                label="Event Date",
                placeholder="Enter the event date",
                custom_id="date",
                default=defaults["date"] if defaults is not None else None,
            )
        )

        self.add_item(
            discord.ui.TextInput(
                label="Event Name",
                placeholder="Enter the event name",
                custom_id="name",
                default=defaults["name"] if defaults is not None else None,
            )
        )

        self.add_item(
            discord.ui.TextInput(
                label="Fansite Handle",
                placeholder="Enter the Twitter handle of the fansite (leave empty to use the official Twitter handle)",
                custom_id="handle",
                default=defaults["handle"] if defaults is not None else None,
            )
        )


class PostChannelView(View):
    def __init__(
        self,
        *,
        timeout: Optional[float] = None,
        input_type: Literal["button", "select"] = "button",
        stop_view: bool = False,
        defer: bool = False,
        images: Optional[List[str]] = None
    ):
        super().__init__(timeout=timeout)

        if images is not None:
            options = [discord.SelectOption(label=f"Image {idx + 1}", description=image, value=image) for idx, image in enumerate(images)]
            self.add_item(
                Select(
                    min_values=1,
                    max_values=len(options),
                    options=options,
                    placeholder="Choose image(s)",
                    row=1,
                    stop_view=stop_view,
                    custom_id="post_channel_image_select",
                    defer=defer
                )
            )

        cmap_conf = CMAutoPostConfig()

        if input_type == "button":
            for channel in cmap_conf.post_channels:
                self.add_item(
                    Button(
                        label=channel["label"], value=channel["id"], custom_id=channel["name"], stop_view=stop_view, defer=defer
                    )
                )
        else:
            options = cmap_conf.generate_post_channel_options()
            self.add_item(
                Select(
                    min_values=1,
                    max_values=len(options),
                    options=options,
                    placeholder="Choose post channel(s)",
                    row=2,
                    stop_view=stop_view,
                    custom_id="post_channel_select",
                    defer=defer
                )
            )

        self.is_confirmed = False

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green, custom_id="confirm", emoji="✔", row=3)
    async def confirm(self, interaction: discord.Interaction, *_):
        self.is_confirmed = True
        self.interaction = interaction
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, custom_id="cancel", emoji="✖️", row=3)
    async def cancel(self, interaction: discord.Interaction, *_):
        self.is_confirmed = False
        self.interaction = interaction
        self.stop()


class PostEmbed(discord.Embed):
    def __init__(self, post_details: Optional[dict] = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.add_field(name="Event Details", value=post_details["event_details"] if post_details is not None and dict_has_key(post_details, "event_details") else "-No event details entered-", inline=False)
        self.add_field(name="Custom Caption", value=post_details["caption"] if post_details is not None and dict_has_key(post_details, "caption") else "-No custom caption entered-", inline=False)

        # TODO: Add previews row
        caption = CMAutoPostConfig.generate_post_caption(post_details)
        self.add_field(name="Caption Preview", value=caption if caption is not None else "-No preview generated-", inline=False)


class CancelView(View):
    def __init__(self, *, timeout: Optional[float] = None):
        super().__init__(timeout=timeout)
        self.interaction = None

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, emoji="✖️")
    async def cancel(self, interaction: discord.Interaction, *_):
        self.interaction = interaction
        self.stop()


class ClearButton(discord.ui.Button):
    async def callback(self, interaction: discord.Interaction):
        del self.view.post_details[self.custom_id.replace('_clear', '')]

        await self.view.embedded_message.edit(embed=PostEmbed(title="Post Details", description="Post details for post INSERT TWITTER LINK HERE by @loonatheworld", post_details=self.view.post_details))

        await interaction.response.defer()

    
class PostView(View):
    def __init__(
        self,
        *,
        timeout: Optional[float] = None,
        bot: discord.Client,
        embedded_message: Union[discord.Message, discord.InteractionMessage],
    ):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.embedded_message = embedded_message
        self.input_names = {
            "event_details": "event details",
            "caption": "custom caption"
        }
        self.post_details = {}
        self.is_confirmed = False

        for idx, input_id in enumerate(self.input_names.keys()):
            self.add_item(
                ClearButton(
                    custom_id=f"{input_id}_clear",
                    emoji="🗑",
                    row=idx
                )
            )


    async def retrieve_user_input(self, interaction: discord.Interaction, button_id: str):
        cmap_conf = CMAutoPostConfig()

        feed_channel = await interaction.guild.fetch_channel(cmap_conf.data["config"]["feed_channel_id"])
        view = CancelView(timeout=90)
        message = await feed_channel.send(content=f"⚠️ Please enter the {self.input_names[button_id]}", view=view)  

        finished, unfinished = await asyncio.wait([self.bot.wait_for('message', check=lambda message: message.author == interaction.user and message.channel == feed_channel), view.wait()], return_when=asyncio.FIRST_COMPLETED)
        
        if isinstance(list(finished)[0].result(), discord.Message):
            user_input = list(finished)[0].result()
            self.post_details[button_id] = user_input.content
            await message.delete()
            await user_input.delete()

            # TODO: Add Twitter link to the Embed
            await self.embedded_message.edit(embed=PostEmbed(title="Post Details", description="Post details for post INSERT TWITTER LINK HERE by @loonatheworld", post_details=self.post_details))
        else:
            await view.interaction.response.send_message(content=f"The {self.input_names[button_id]} was not recorded", ephemeral=True)
        
        for task in unfinished:
            task.cancel()
        

    @discord.ui.button(label="Event Details", style=discord.ButtonStyle.primary, custom_id="event_details", emoji="📆", row=0)
    async def event_details(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.retrieve_user_input(interaction=interaction, button_id=button.custom_id)

    @discord.ui.button(label="Custom Caption", style=discord.ButtonStyle.primary, custom_id="caption", emoji="⚠️", row=3)
    async def custom(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.retrieve_user_input(interaction=interaction, button_id=button.custom_id)

    @discord.ui.button(label="Save", style=discord.ButtonStyle.green, custom_id="save", emoji="✔", row=4)
    async def save(self, interaction: discord.Interaction, *_):
        self.is_confirmed = True
        self.interaction = interaction
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, custom_id="cancel", emoji="✖️", row=4)
    async def cancel(self, interaction: discord.Interaction, *_):
        self.is_confirmed = False
        self.interaction = interaction
        self.stop()


class PersistentPostChannelButton(discord.ui.Button):
    def __init__(
        self,
        *,
        style: discord.ButtonStyle = discord.ButtonStyle.primary,
        label: Optional[str] = None,
        disabled: bool = False,
        custom_id: Optional[str] = None,
        url: Optional[str] = None,
        emoji: Optional[Union[str, discord.Emoji, discord.PartialEmoji]] = None,
        row: Optional[int] = None,
        value: Any,
        files: List[discord.File]
    ):
        super().__init__(
            style=style, label=label, disabled=disabled, custom_id=custom_id, url=url, emoji=emoji, row=row
        )
        self.value = value
        self.files = files

    
    async def callback(self, interaction: discord.Interaction):
        if self.value == "stop":
            self.view.stop()
            self.view.interaction = interaction
            return

        post_modal = PostModal(
            title="Create Post",
            custom_id="create_post_modal",
            success_msg="The post details was successfully recorded!",
            error_msg="A few problems were encountered when recording the post details, please try again!",
        )

        await interaction.response.send_modal(post_modal)
        timeout = await post_modal.wait()

        if timeout:
            await interaction.followup.send(content="The command has timed out, please try again!", ephemeral=True)
            return
        
        # Post
        post_channel = await interaction.guild.fetch_channel(int(self.value))
        post_details = post_modal.get_values()
        content = f'```ml\n{post_details["date"]} {post_details["name"]} | cr: {post_details["handle"]} (@INSERT_TWITTER_HANDLE)\n```'
        await post_channel.send(content=content, files=[discord.File(fp=f"loonatheworld/{f}") for f in self.files])
        await interaction.followup.send(content=f"Post successfully created in <#{post_channel.id}>")


class PersistentPostView(View):
    def __init__(self, *, timeout: Optional[float] = None, **kwargs):
        super().__init__(timeout=timeout)

        if kwargs != {}:
            self.message_id = kwargs["message_id"]

            cmap_conf = CMAutoPostConfig()

            for channel in cmap_conf.post_channels:
                self.add_item(
                    PersistentPostChannelButton(
                        label=channel["label"], value=channel["id"], custom_id=f"persistent:{self.message_id}:{channel['name']}", files=kwargs["files"]
                    )
                )

            self.add_item(
                PersistentPostChannelButton(
                    style=discord.ButtonStyle.red,
                    custom_id=f"persistent:{self.message_id}:stop",
                    emoji="✖️",
                    value="stop",
                    files=kwargs["files"]
                )
            )


class PersistentTweetButton(discord.ui.Button):
    def __init__(
        self,
        *,
        style: discord.ButtonStyle = discord.ButtonStyle.primary,
        label: Optional[str] = None,
        disabled: bool = False,
        custom_id: Optional[str] = None,
        url: Optional[str] = None,
        emoji: Optional[Union[str, discord.Emoji, discord.PartialEmoji]] = None,
        row: Optional[int] = None,
        callback_type: Literal["select", "all", "stop"],
        filenames: List[str],
        bot: Any,
    ):
        super().__init__(
            style=style, label=label, disabled=disabled, custom_id=custom_id, url=url, emoji=emoji, row=row
        )
        self.filenames = filenames
        self.callback_type = callback_type
        self.callbacks = {
            "select": self.select,
            "all": self.all,
            "stop": self.stop
        }
        self.bot = bot

    async def send_post_modal(self, interaction: discord.Interaction):
        post_modal = PostModal(
            title="Create Post",
            custom_id="create_post_modal",
            success_msg="The post details was successfully recorded!",
            error_msg="A few problems were encountered when recording the post details, please try again!",
        )

        await interaction.response.send_modal(post_modal)
        timeout = await post_modal.wait()

        if timeout:
            await interaction.followup.send(content="The command has timed out, please try again!", ephemeral=True)
            return
        
        return post_modal.get_values(), post_modal.interaction

    async def send_post_channel_view(self, interaction: discord.Interaction, images: Optional[List[str]] = None):
        post_channel_view = PostChannelView(
            timeout=90,
            input_type="select",
            stop_view=False,
            defer=True,
            images=images
        )

        if images is not None:
            content = "Choose the image(s) that you want to post and channel(s) that you want to post the images in:"
        else:
            content = "Choose the channel(s) that you want to post in:"

        await interaction.response.send_message(content=content, view=post_channel_view)
        timeout = await post_channel_view.wait()
        await interaction.delete_original_response()

        if timeout:
            await interaction.followup.send(content="The command has timed out, please try again!", ephemeral=True)
            return None
        elif not post_channel_view.is_confirmed and post_channel_view.dict_values == {}:
            await interaction.followup.send(content="No post was sent", ephemeral=True)
            return None
        
        return (post_channel_view.dict_values, post_channel_view.interaction)

    async def select(self, interaction: discord.Interaction):
        res = await self.send_post_channel_view(interaction, self.filenames)

        if res is None:
            return

        post_channel, post_channel_view_interaction = res
        post_channel_ids = post_channel["post_channel_select"]
        selected_images = post_channel["post_channel_image_select"]

        await post_channel_view_interaction.response.send_message(embed=PostEmbed(title="Post Details", description="Post details for post INSERT TWITTER LINK HERE by @loonatheworld"))
        embedded_message = await post_channel_view_interaction.original_response()
        view = PostView(bot=self.bot, embedded_message=embedded_message, timeout=90)
        await post_channel_view_interaction.edit_original_response(view=view)
        
        timeout = await view.wait()

        await post_channel_view_interaction.edit_original_response(view=None)

        if timeout:
            await interaction.followup.send(content="The command has timed out, please try again!", ephemeral=True)
        elif view.is_confirmed:
            caption = CMAutoPostConfig.generate_post_caption(view.post_details)

            if caption is not None:
                channels = []
                for post_channel_id in post_channel_ids:
                    channel = await interaction.guild.fetch_channel(int(post_channel_id))
                    await channel.send(content=caption, files=[discord.File(fp=f"loonatheworld/{f}") for f in selected_images])
                    channels.append(f"<#{channel.id}>")

                await post_channel_view_interaction.followup.send(content=f"Post(s) successfully created in {', '.join(channels)}")
            else:
                await post_channel_view_interaction.followup.send(content=f"No post(s) created in {', '.join(channels)} as no captions were provided")
        else:
            await interaction.followup.send(content="Posting cancelled", ephemeral=True)
        

    async def all(self, interaction: discord.Interaction):
        post_channel, post_channel_view_interaction = await self.send_post_channel_view(interaction)
        post_channel_ids = post_channel["post_channel_select"]

        await post_channel_view_interaction.response.send_message(embed=PostEmbed(title="Post Details", description="Post details for post INSERT TWITTER LINK HERE by @loonatheworld"))
        embedded_message = await post_channel_view_interaction.original_response()
        view = PostView(bot=self.bot, embedded_message=embedded_message, timeout=90)
        await post_channel_view_interaction.edit_original_response(view=view)
        
        timeout = await view.wait()

        await post_channel_view_interaction.edit_original_response(view=None)

        if timeout:
            await interaction.followup.send(content="The command has timed out, please try again!", ephemeral=True)
        elif view.is_confirmed:
            caption = CMAutoPostConfig.generate_post_caption(view.post_details)

            if caption is not None:
                channels = []
                for post_channel_id in post_channel_ids:
                    channel = await post_channel_view_interaction.guild.fetch_channel(int(post_channel_id))
                    await channel.send(content=caption, files=[discord.File(fp=f"loonatheworld/{f}") for f in self.filenames])
                    channels.append(f"<#{channel.id}>")

                await post_channel_view_interaction.followup.send(content=f"Post(s) successfully created in {', '.join(channels)}")
            else:
                await post_channel_view_interaction.followup.send(content=f"No post(s) created in {', '.join(channels)} as no captions were provided")
        else:
            await interaction.followup.send(content="Posting cancelled", ephemeral=True)

    async def stop(self, interaction: discord.Interaction):
        self.view.stop()
        self.view.interaction = interaction

    async def callback(self, interaction: discord.Interaction):
        await self.callbacks.get(self.callback_type, None)(interaction)


class PersistentTweetView(View):
    def __init__(self, *, timeout: Optional[float] = None, **kwargs):
        super().__init__(timeout=timeout)

        if kwargs != {}:
            self.message_id = kwargs["message_id"]
            self.filenames = kwargs["filenames"]
            self.bot = kwargs["bot"]

            self.add_item(
                PersistentTweetButton(
                    label="Select Images",
                    style=discord.ButtonStyle.primary,
                    custom_id=f"persistent:{self.message_id}:select",
                    callback_type="select",
                    filenames=self.filenames,
                    bot=self.bot
                )
            )

            self.add_item(
                PersistentTweetButton(
                    label="All Images",
                    style=discord.ButtonStyle.primary,
                    custom_id=f"persistent:{self.message_id}:all",
                    callback_type="all",
                    filenames=self.filenames,
                    bot=self.bot
                )
            )

            self.add_item(
                PersistentTweetButton(
                    style=discord.ButtonStyle.red,
                    custom_id=f"persistent:{self.message_id}:stop",
                    emoji="✖️",
                    callback_type="stop",
                    filenames=self.filenames,
                    bot=self.bot
                )
            )
