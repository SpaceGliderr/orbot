import asyncio
from operator import itemgetter
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
                    min_values=0,
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
                    min_values=0,
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
        self.images = images

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green, custom_id="confirm", emoji="✔", row=3)
    async def confirm(self, interaction: discord.Interaction, *_):
        # TODO: Add a check here to see whether user actually selected anything
        missing_fields = []
        if self.images is not None: 
            if not dict_has_key(self.dict_values, "post_channel_image_select"):
                missing_fields.append("image(s)")
            elif len(self.dict_values["post_channel_image_select"]) == 0:
                missing_fields.append("image(s)")

        if not dict_has_key(self.dict_values, "post_channel_select"):
            missing_fields.append("channel(s)")
        elif len(self.dict_values["post_channel_select"]) == 0:
            missing_fields.append("channel(s)")
        
        if len(missing_fields) != 0:
            await interaction.response.send_message(content=f"Please select {' and '.join(missing_fields)} to create post", ephemeral=True)
            return

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
        
        caption = CMAutoPostConfig.generate_post_caption(post_details)

        self.add_field(name="Event Details", value=f'{post_details["event_details"]}\n\u200B' if post_details is not None and dict_has_key(post_details, "event_details") else "-No event details entered-\n\u200B", inline=False)
        self.add_field(name="Custom Caption", value=f'{post_details["caption"]}\n\u200B' if post_details is not None and dict_has_key(post_details, "caption") else "-No custom caption entered-\n\u200B", inline=False)
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

        await self.view.embedded_message.edit(embed=PostEmbed(title="Post Details", description="Post details for post INSERT TWITTER LINK HERE by @loonatheworld\n\u200B", post_details=self.view.post_details))

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

        self.input_message = None
        self.is_cancelled = False


    async def retrieve_user_input(self, interaction: discord.Interaction, button_id: str):
        cmap_conf = CMAutoPostConfig()

        feed_channel = await interaction.guild.fetch_channel(cmap_conf.data["config"]["feed_channel_id"])
        
        embed = discord.Embed(title=f"Enter the {self.input_names[button_id]}", description=f"The next message you send in <#{feed_channel.id}> will be recorded as the {self.input_names[button_id]}")
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.avatar)
        embed.set_footer(text="Data is recorded successfully when the previous embed is updated with the data.")

        view = CancelView(timeout=30)
        message = await feed_channel.send(embed=embed, view=view) # TODO: Do an embed

        self.input_message = message

        finished, unfinished = await asyncio.wait([self.bot.wait_for('message', check=lambda message: message.author == interaction.user and message.channel == feed_channel), view.wait()], return_when=asyncio.FIRST_COMPLETED)

        for task in unfinished:
            task.cancel()

        # TODO: Keep track of unfinished tasks and message sent, when the cancel button is clicked, delete all of that and remove the coroutines
        if self.is_cancelled:
            print("Cancelled effective")
            return

        if isinstance(list(finished)[0].result(), discord.Message):
            user_input = list(finished)[0].result()
            self.post_details[button_id] = user_input.content
            await user_input.delete()
            await message.delete()
            
            # TODO: Add Twitter link to the Embed
            await self.embedded_message.edit(embed=PostEmbed(title="Post Details", description="Post details for post INSERT TWITTER LINK HERE by @loonatheworld\n\u200B", post_details=self.post_details))
            return

        elif list(finished)[0].result(): # True signifies that it is timed out
            await view.interaction.response.send_message(content=f"The user input timed out, please try again!", ephemeral=True)
        else: # False signifies the cancel button was clicked
            await view.interaction.response.send_message(content=f"The {self.input_names[button_id]} was not entered", ephemeral=True)
        
        await message.delete()
        

    @discord.ui.button(label="Event Details", style=discord.ButtonStyle.primary, custom_id="event_details", emoji="📆", row=0)
    async def event_details(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.retrieve_user_input(interaction=interaction, button_id=button.custom_id)

    @discord.ui.button(label="Custom Caption", style=discord.ButtonStyle.primary, custom_id="caption", emoji="⚠️", row=1)
    async def custom(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.retrieve_user_input(interaction=interaction, button_id=button.custom_id)

    @discord.ui.button(label="Post", style=discord.ButtonStyle.green, custom_id="post", emoji="📮", row=2)
    async def post(self, interaction: discord.Interaction, *_):
        # TODO: Check whether caption is generated
        caption = CMAutoPostConfig.generate_post_caption(self.post_details)

        if caption is None:
            await interaction.response.send_message(content="Please enter a caption before posting", ephemeral=True)
            return

        self.is_confirmed = True
        self.interaction = interaction
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, custom_id="cancel", emoji="✖️", row=2)
    async def cancel(self, interaction: discord.Interaction, *_):
        if self.input_message is not None:
            print("Deleting message")
            await self.input_message.delete()

        self.is_cancelled = True
        self.is_confirmed = False
        self.interaction = interaction
        self.stop()


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
        elif not post_channel_view.is_confirmed:
            await interaction.followup.send(content="No post was sent", ephemeral=True)
        else:
            await self.send_post_view(post_channel_view.interaction, post_channel_view.dict_values, images)


    async def send_post_view(self, interaction: discord.Interaction, values: dict, images: Optional[List[str]] = None):
        post_channel_ids = values["post_channel_select"]
        images_to_post = values["post_channel_image_select"] if images is not None and self.callback_type == "select" else self.filenames

        await interaction.response.send_message(embed=PostEmbed(title="Post Details", description="Post details for post INSERT TWITTER LINK HERE by @loonatheworld\n\u200B"))
        embedded_message = await interaction.original_response()
        view = PostView(bot=self.bot, embedded_message=embedded_message, timeout=90)
        await interaction.edit_original_response(view=view)

        timeout = await view.wait()

        await interaction.edit_original_response(view=None)

        if timeout:
            await interaction.followup.send(content="The command has timed out, please try again!", ephemeral=True)
        elif view.is_confirmed:
            caption = CMAutoPostConfig.generate_post_caption(view.post_details)

            post_channels = []
            for post_channel_id in post_channel_ids:
                post_channel = await interaction.guild.fetch_channel(int(post_channel_id))
                await post_channel.send(content=caption, files=[discord.File(fp=f"loonatheworld/{fp}") for fp in images_to_post])
                post_channels.append(f"<#{post_channel.id}>")

            await interaction.followup.send(content=f"Post(s) successfully created in {', '.join(post_channels)}")
    

    async def select(self, interaction: discord.Interaction):
        await self.send_post_channel_view(interaction, self.filenames)

    async def all(self, interaction: discord.Interaction):
        await self.send_post_channel_view(interaction)

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


class EditPostButton(discord.ui.Button):
    def __init__(
        self,
        callback_type: Literal["edit_caption", "add_image", "remove_image", "stop"],
        bot: Any,
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.callback_type = callback_type
        self.callbacks = {
            "edit_caption": self.edit_caption,
            "add_image": self.add_image,
            "remove_image": self.remove_image,
            "save": self.save,
            "stop": self.stop
        }
        self.bot = bot
        self.is_cancelled = False

    async def edit_caption(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=PostEmbed(title="Post Details", description="Post details for post INSERT TWITTER LINK HERE by @loonatheworld\n\u200B"))
        embedded_message = await interaction.original_response()
        view = PostView(bot=self.bot, embedded_message=embedded_message, timeout=90)
        await interaction.edit_original_response(view=view)

        timeout = await view.wait()

        await interaction.edit_original_response(view=None)

        if timeout:
            await interaction.followup.send(content="The command has timed out, please try again!", ephemeral=True)
        elif view.is_confirmed:
            caption = CMAutoPostConfig.generate_post_caption(view.post_details)
            self.view.post_details["caption"] = caption
            await self.view.embedded_message.edit(embed=EditPostEmbed(post_details=self.view.post_details))
            await embedded_message.delete()

    async def add_image(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        cmap_conf = CMAutoPostConfig()

        feed_channel = await interaction.guild.fetch_channel(cmap_conf.data["config"]["feed_channel_id"])
        
        embed = discord.Embed(title=f"Enter the new images", description=f"The next message you send in <#{feed_channel.id}> will be recorded as the new images")
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.avatar)
        embed.set_footer(text="Data is recorded successfully when the previous embed is updated with the data.")

        view = CancelView(timeout=30)
        message = await feed_channel.send(embed=embed, view=view) # TODO: Do an embed

        self.input_message = message

        finished, unfinished = await asyncio.wait([self.bot.wait_for('message', check=lambda message: message.author == interaction.user and message.channel == feed_channel), view.wait()], return_when=asyncio.FIRST_COMPLETED)

        for task in unfinished:
            task.cancel()

        # TODO: Keep track of unfinished tasks and message sent, when the cancel button is clicked, delete all of that and remove the coroutines
        if self.is_cancelled:
            print("Cancelled effective")
            return

        if isinstance(list(finished)[0].result(), discord.Message):
            user_input = list(finished)[0].result()
            self.view.post_details["files"].extend([await attachment.to_file() for attachment in user_input.attachments])
            await user_input.delete()
            await message.delete()
            
            # TODO: Add Twitter link to the Embed
            await self.view.embedded_message.edit(embed=EditPostEmbed(post_details=self.view.post_details))
            # await self.embedded_message.edit(embed=PostEmbed(title="Post Details", description="Post details for post INSERT TWITTER LINK HERE by @loonatheworld\n\u200B", post_details=self.post_details))
            return

        elif list(finished)[0].result(): # True signifies that it is timed out
            await interaction.followup.send(content=f"The user input timed out, please try again!", ephemeral=True)
        else: # False signifies the cancel button was clicked
            await interaction.followup.send(content=f"The images was not entered", ephemeral=True)
        
        await message.delete()

    async def remove_image(self, interaction: discord.Interaction):
        view = View()
        options = [discord.SelectOption(label=f"Image {idx + 1}", description=f.filename, value=idx, default=True) for idx, f in enumerate(self.view.post_details["files"])]
        view.add_item(
            Select(
                min_values=0,
                max_values=len(options),
                options=options,
                placeholder="Choose image(s) to remove",
                stop_view=True,
                custom_id="keep_image_select",
                defer=True
            )
        )
        
        await interaction.response.send_message(content="Please select the image(s) to keep", view=view)
        await view.wait()
        await interaction.delete_original_response()

        print(view.dict_values)

        if dict_has_key(view.dict_values, "keep_image_select"):
            index_list = [int(idx) for idx in view.dict_values["keep_image_select"]]
            self.view.post_details["files"] = list(map(list(self.view.post_details["files"]).__getitem__, index_list))

            await self.view.embedded_message.edit(embed=EditPostEmbed(post_details=self.view.post_details))
            return
        
        await interaction.followup.send(content="No images were removed")
        

    async def save(self, interaction: discord.Interaction):
        

        # TODO: Edit original post
        if len(self.view.post_details["files"]) != 0:
            print("SUCCESS")
            await interaction.response.defer()
            await self.view.post_details["message"].edit(content=self.view.post_details["caption"], attachments=self.view.post_details["files"])
            print(interaction)
            print(self.view.interaction)
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


class EditPostView(View):
    def __init__(self, *, timeout: Optional[float] = None, post_details: dict, embedded_message: Union[discord.Message, discord.InteractionMessage], bot: discord.Client):
        super().__init__(timeout=timeout)

        self.post_details = post_details
        self.embedded_message = embedded_message
        self.message_id = embedded_message.id
        self.bot = bot
        self.is_confirmed = False
        print(post_details["files"])

        self.add_item(
            EditPostButton(
                label="Edit Caption",
                style=discord.ButtonStyle.primary,
                custom_id=f"{self.message_id}:edit_caption",
                callback_type="edit_caption",
                bot=self.bot
            )
        )

        self.add_item(
            EditPostButton(
                label="Add Image(s)",
                style=discord.ButtonStyle.primary,
                custom_id=f"{self.message_id}:add_image",
                callback_type="add_image",
                bot=self.bot
            )
        )

        self.add_item(
            EditPostButton(
                label="Remove Image(s)",
                style=discord.ButtonStyle.primary,
                custom_id=f"{self.message_id}:remove_image",
                callback_type="remove_image",
                bot=self.bot
            )
        )

        self.add_item(
            EditPostButton(
                style=discord.ButtonStyle.green,
                custom_id=f"{self.message_id}:save",
                emoji="✔️",
                callback_type="save",
                bot=self.bot
            )
        )
        
        self.add_item(
            EditPostButton(
                style=discord.ButtonStyle.red,
                custom_id=f"{self.message_id}:stop",
                emoji="✖️",
                callback_type="stop",
                bot=self.bot
            )
        )


class EditPostEmbed(discord.Embed):
    def __init__(self, post_details: dict, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.title = "Edit Post"
        self.description = f"Edits the post made in <#{post_details['message'].channel.id}> with a message ID of {post_details['message'].id}"

        self.add_field(name="Caption", value=post_details["caption"], inline=False)
        self.add_field(name="Files", value=', '.join([f.filename for f in post_details["files"]]) if len(post_details["files"]) != 0 else "-No files were uploaded-", inline=False)
