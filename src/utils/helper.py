import io
import zipfile
from functools import reduce
from typing import List, Optional

import aiohttp
import discord


def get_from_dict(dic, map_list):
    """Iterate nested dictionary"""
    try:
        return reduce(dict.get, map_list, dic)
    except TypeError:
        return None


def dict_has_key(dic, key):
    return key in dic.keys()


async def download_files(urls: List[str], filenames: Optional[List[str]] = None):
    if filenames is not None and len(filenames) != len(urls):
        raise Exception
    return [
        await download_file(url, filenames[idx] if filenames is not None else idx + 1) for idx, url in enumerate(urls)
    ]


async def download_file(url: str, name: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                raise Exception("Cannot download file")
            data = io.BytesIO(await resp.read())
            return discord.File(data, name)


async def convert_files_to_zip(files: List[discord.File], filename: Optional[str] = None):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        for discord_file in files:
            zip_file.writestr(discord_file.filename, discord_file.fp.getvalue())

    zip_buffer.seek(0)
    filename = f"{filename}.zip" if filename is not None else "images.zip"
    return discord.File(zip_buffer, filename)
