from functools import reduce

import io
from typing import List
import aiohttp
import discord
import zipfile


def get_from_dict(dic, map_list):
    """Iterate nested dictionary"""
    try:
        return reduce(dict.get, map_list, dic)
    except TypeError:
        return None


def dict_has_key(dic, key):
    return key in dic.keys()


async def download_files(urls: List[str]):
    return [await download_file(url, idx) for idx, url in enumerate(urls)]


async def download_file(url: str, name: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                raise Exception("Cannot download file")
            data = io.BytesIO(await resp.read())
            return discord.File(data, f'{name}.png')


async def convert_files_to_zip(files: List[discord.File]):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        for discord_file in files:
            zip_file.writestr(discord_file.filename, discord_file.fp.getvalue())
                    
    zip_buffer.seek(0)
    return discord.File(zip_buffer, "images.zip")
