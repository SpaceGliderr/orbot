from typing import List, Tuple, TypedDict

import discord
from typing_extensions import NotRequired


class TweetDetails(TypedDict):
    user: TypedDict("TwitterUser", {"id": str, "name": str, "username": str})
    url: str


class PostDetails(TypedDict):
    message: NotRequired[discord.Message | None]
    caption: NotRequired[str | None]
    caption_credits: NotRequired[Tuple[str, str] | None]
    channels: NotRequired[List[str] | None]
    files: List[discord.File]
    tweet_url: NotRequired[str | None]


class PostCaptionDetails(TypedDict):
    caption: NotRequired[str | None]
    default: NotRequired[str | None]
    has_credits: bool
