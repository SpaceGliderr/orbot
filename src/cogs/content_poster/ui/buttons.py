from typing import List, Literal, Tuple

import discord

from src.cogs.content_poster.ui.embeds import (
    PostCaptionEmbed,
    PostDetailsEmbed,
    set_embed_author,
)
from src.utils.helper import dict_has_key


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

        await self.view.embedded_message.edit(
            embed=set_embed_author(interaction=interaction, embed=PostDetailsEmbed(post_details=self.post_details))
        )


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
            embed=set_embed_author(
                interaction=interaction,
                embed=PostCaptionEmbed(
                    url=self.post_url,
                    embed_type=self.embed_type,
                    caption_credits=self.caption_credits,
                    post_caption_details=self.view.post_details,
                ),
            )
        )

        await interaction.response.defer()
