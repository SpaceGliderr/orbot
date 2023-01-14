import io
import zipfile
from dataclasses import _MISSING_TYPE, MISSING
from functools import reduce
from typing import List, Literal, Optional, Sequence

import aiohttp
import discord


def get_from_dict(dic, map_list):
    """Iterate nested dictionary. Returns `None` if not key is not found."""
    try:
        return reduce(dict.get, map_list, dic)
    except TypeError:
        return None


def dict_has_key(dic, key):
    """Whether or not a dictionary has a given key. Returns `True` or `False`"""
    return key in dic.keys()


async def download_files(urls: List[str], filenames: Optional[List[str]] = None):
    """Downloads multiple files from a list of urls. Returns a list of downloaded `discord.Files`.

    Parameters
    ----------
        * urls: List[:class:`str`]
            - The urls to download.
        * filenames: Optional[List[`str`]] | None
            - The filenames for the urls. Must be equal to the number of urls, otherwise it raises an `Exception`.
    """
    if filenames is not None and len(filenames) != len(urls):
        raise Exception
    return [
        await download_file(url, filenames[idx] if filenames is not None else idx + 1) for idx, url in enumerate(urls)
    ]


async def download_file(url: str, name: str):
    """Downloads a single file. Returns a downloaded `discord.File` instance.

    Parameters
    ----------
        * url: :class:`str`
            - The url to download.
        * name: :class:`str`
            - The name of the downloaded file.
    """
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                raise Exception("Cannot download file")
            data = io.BytesIO(await resp.read())
            return discord.File(data, name)


async def convert_files_to_zip(files: List[discord.File], filename: Optional[str] = None):
    """Converts a list of `discord.File`s to a ZIP file.

    Parameters
    ----------
        * files: List[:class:`discord.File`]
            - The list of files to compress into a ZIP file.
        * filename: Optional[:class:`str`] | None
            - The name of the ZIP file.
    """
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        for discord_file in files:
            zip_file.writestr(discord_file.filename, discord_file.fp.getvalue())

    zip_buffer.seek(0)
    filename = f"{filename}.zip" if filename is not None else "images.zip"
    return discord.File(zip_buffer, filename)


async def send_or_edit_interaction_message(
    interaction: discord.Interaction,
    edit_original_response: Optional[bool] = False,
    content: Optional[str] = None,
    embed: Optional[discord.Embed] = MISSING,
    embeds: Optional[List[discord.Embed]] = MISSING,
    file: Optional[discord.File] = MISSING,
    files: Optional[List[discord.File]] = MISSING,
    tts: Optional[bool] = False,
    view: Optional[discord.ui.View] = MISSING,
    ephemeral: Optional[bool] = False,
    allowed_mentions: Optional[discord.AllowedMentions] = None,
    suppress_embeds: Optional[bool] = False,
    delete_after: Optional[float] = None,
    attachments: Optional[Sequence[discord.Attachment | discord.File]] = MISSING,
):
    kwargs = {}

    if not isinstance(view, _MISSING_TYPE):
        kwargs["view"] = view

    if not isinstance(embed, _MISSING_TYPE):
        kwargs["embed"] = embed

    if not isinstance(embeds, _MISSING_TYPE):
        kwargs["embeds"] = embeds

    if not isinstance(file, _MISSING_TYPE) and (not interaction.response.is_done() or not edit_original_response):
        kwargs["file"] = file

    if not isinstance(files, _MISSING_TYPE) and (not interaction.response.is_done() or not edit_original_response):
        kwargs["files"] = files

    if not isinstance(attachments, _MISSING_TYPE) and interaction.response.is_done() and edit_original_response:
        kwargs["attachments"] = attachments

    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(
                content=content,
                tts=tts,
                ephemeral=ephemeral,
                allowed_mentions=allowed_mentions,
                suppress_embeds=suppress_embeds,
                delete_after=delete_after,
                **kwargs,
            )
            return await interaction.original_response()
        elif edit_original_response:
            try:
                await interaction.edit_original_response(content=content, allowed_mentions=allowed_mentions, **kwargs)
                return await interaction.original_response()
            except discord.errors.NotFound:
                return await interaction.followup.send(
                    content=content,
                    wait=True,
                    tts=tts,
                    ephemeral=ephemeral,
                    allowed_mentions=allowed_mentions,
                    suppress_embeds=suppress_embeds,
                    **kwargs,
                )
        else:
            return await interaction.followup.send(
                content=content,
                wait=True,
                tts=tts,
                ephemeral=ephemeral,
                allowed_mentions=allowed_mentions,
                suppress_embeds=suppress_embeds,
                **kwargs,
            )
    except Exception as e:
        if not interaction.response.is_done():
            await interaction.response.send_message(
                content="Error occurred while sending a message.", ephemeral=True, delete_after=10
            )
            return await interaction.original_response()
        else:
            return await interaction.followup.send(
                content="Error occurred while sending a message.", wait=True, ephemeral=True
            )
