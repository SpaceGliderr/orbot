import asyncio
from typing import Awaitable, Callable, List, Optional

import discord

from src.modules.ui.custom import CancelView
from src.utils.config import ContentPosterConfig


async def send_input_message(bot: discord.Client, input_name: str, interaction: discord.Interaction):
    cp_conf = ContentPosterConfig()
    feed_channel = cp_conf.get_feed_channel(bot)

    user_input_embed = discord.Embed(
        title=f"Enter {input_name}",
        description=f"The next message you send in <#{feed_channel.id}> will be recorded as the {input_name}",
    )
    user_input_embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.avatar)
    user_input_embed.set_footer(text="Data is recorded successfully when the previous embed is updated with the data.")

    cancel_view = CancelView(timeout=60)

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

