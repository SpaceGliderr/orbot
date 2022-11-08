import io
import zipfile
from functools import reduce
from typing import List, Optional

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
