from functools import reduce

import io
from typing import List
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


async def download_files(urls: List[str]):
    return [await download_file(url, idx) for idx, url in enumerate(urls)]


async def download_file(url: str, name: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                raise Exception("Cannot download file")
            data = io.BytesIO(await resp.read())
            return discord.File(data, f'{name}.png')
