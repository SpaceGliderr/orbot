from typing import Literal, Optional, Tuple

import discord

from src.typings.content_poster import PostCaptionDetails, PostDetails
from src.utils.config import ContentPosterConfig
from src.utils.helper import dict_has_key


def set_embed_author(interaction: discord.Interaction, embed: discord.Embed):
    """Helper function that sets the embed author based on an interaction object."""
    return embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.avatar)


class PostCaptionEmbed(discord.Embed):
    """Creates an embed that shows the Post Caption details by inheriting the `discord.Embed` class.

    Additional Parameters
    ----------
        * embed_type: Literal[`new`, `edit`]
            - Determines the verb of the embeds `title` and `description`.
        * caption_credits: Optional[Tuple[:class:`str`, :class:`str`]] | None
            - The anatomized caption credits. The first element is the Twitter name, the second element is the Twitter handle.
        * post_caption_details: Optional[:class:`dict`] | None
            - The post details to display in the embed. Possible keys: `caption`.
    """

    def __init__(
        self,
        embed_type: Literal["new", "edit"],
        caption_credits: Optional[Tuple[str, str]] = None,
        post_caption_details: Optional[PostCaptionDetails] = None,
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
            name="Caption Content",
            value=f'{post_caption_details["caption"]}\n\u200B'
            if post_caption_details is not None and dict_has_key(post_caption_details, "caption")
            else "_-No content entered-_\n\u200B",
            inline=False,
        )
        self.add_field(
            name="Caption Credits",
            value="_No credits available_\n\u200B"
            if caption_credits is None
            else "Credits enabled\n\u200B"
            if post_caption_details["has_credits"]
            else "Credits disabled\n\u200B",
            inline=False,
        )
        self.add_field(
            name="Caption Preview", value=caption if caption is not None else "_-No preview generated-_", inline=False
        )


class PostDetailsEmbed(discord.Embed):
    """Creates an embed that shows the Post details by inheriting the `discord.Embed` class. Only shown when editing a post.

    Additional Parameters
    ----------
        * post_details: :type:`PostDetails`
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
