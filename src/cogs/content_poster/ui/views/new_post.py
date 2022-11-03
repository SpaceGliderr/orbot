import asyncio
from operator import itemgetter
from typing import List, Union

import discord

from src.cogs.content_poster.ui.buttons import NewClearButton
from src.cogs.content_poster.ui.embeds import PostDetailsEmbed, set_embed_author
from src.cogs.content_poster.ui.views.post_details import (
    PostChannelView,
    PostMediaView,
    get_post_caption,
    send_post_caption_view,
)
from src.typings.content_poster import PostDetails, TweetDetails
from src.utils.config import ContentPosterConfig
from src.utils.helper import dict_has_key, get_from_dict
from src.modules.ui.common import Button, View


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
                        "label": "Make Caption",
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

    async def caption(self, interaction: discord.Interaction, *_):
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
            await self.embedded_message.edit(
                embed=set_embed_author(interaction=interaction, embed=PostDetailsEmbed(post_details=self.post_details))
            )

    async def channel(self, interaction: discord.Interaction, *_):
        post_details_view = PostChannelView(
            timeout=120,
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
                self.embedded_message.edit(
                    embed=set_embed_author(
                        interaction=interaction, embed=PostDetailsEmbed(post_details=self.post_details)
                    )
                ),
            )

    async def select(self, interaction: discord.Interaction, *_):
        post_medias_view = PostMediaView(
            timeout=120, images=self.files, stop_view=False, defer=True, defaults=self.post_details["files"]
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
                self.embedded_message.edit(
                    embed=set_embed_author(
                        interaction=interaction, embed=PostDetailsEmbed(post_details=self.post_details)
                    )
                ),
            )

    async def post(self, interaction: discord.Interaction, *_):
        if get_from_dict(self.post_details, ["caption"]) is None or len(self.post_details["files"]) == 0:
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

    async def cancel(self, interaction: discord.Interaction, *_):
        await self.embedded_message.delete()
        await self.stop_active_views()
        self.stop()
        self.interaction = interaction
