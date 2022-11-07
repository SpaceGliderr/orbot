import asyncio
import math
import threading
from datetime import datetime
from typing import List, Union

import discord
from dateutil import parser
from tweepy.asynchronous import AsyncClient

from src.cogs.content_poster.ui.embeds import set_embed_author
from src.modules.twitter.feed import TwitterFeed
from src.modules.ui.custom import PaginatedEmbedsView


def add_field_to_embed(
    ids_to_prune: List[int],
    pruned_account_embeds: List[discord.Embed],
    embed: discord.Embed,
    user_id: int,
    user: Union[dict, None],
    reason: str,
):
    ids_to_prune.append(user_id)

    embed.add_field(
        name=f"{user['name']} @{user['username']}" if user is not None else user_id, value=reason, inline=False
    )

    if len(ids_to_prune) % 25 == 0:
        pruned_account_embeds.append(embed)
        embed = discord.Embed()

    return ids_to_prune, pruned_account_embeds, embed


async def prune_accounts(duration: int, twitter_client: AsyncClient):
    user_ids = TwitterFeed.get_user_ids()
    ids_to_prune = []
    pruned_account_embeds = []

    embed = discord.Embed()

    for idx, user_id in enumerate(user_ids):
        # Get the 5 most recent tweets from a given user ID
        result = await twitter_client.get_users_tweets(
            id=user_id, max_results=5, tweet_fields=["created_at"], expansions="author_id"
        )

        user = None  # Store user object
        search_user = True
        reason = ""

        if (
            len(result.errors) != 0
        ):  # If there is an error, it means that the account is protected and the tweets cannot be accessed
            reason = "_<Account privated>_"
        else:
            try:
                # Access the most recent tweet
                recent_tweet_date = parser.parse(result.data[0].data["created_at"]).date()
                date_diff = datetime.now().date() - recent_tweet_date  # Find duration of the last post

                search_user = False  # Prevents additional unnecessary API calls

                if (
                    date_diff.days > duration
                ):  # Check whether the days since the last post exceeds specified duration threshold
                    reason = f"_Last Tweet on {recent_tweet_date}, {date_diff.days} days ago_"
                    user = result.includes["users"][0].data  # Store user
            except:  # Handles error thrown by accessing an empty object (no tweets available)
                reason = "_<Account has no Tweets>_"

        if search_user:
            # Get the user information of the user ID
            # Cannot obtain user information from `get_users_tweets` as in the case when a user has not posted any tweets,
            # `get_users_tweets` will return an empty object for the user even though the user exists
            user_response = await twitter_client.get_user(id=user_id, user_fields=["name", "username"])

            if user_response.data is not None:
                user = user_response.data.data
            else:  # If user can't be found, means it is deleted or does not exist
                reason = "_<Account deleted or does not exist>_"

        if reason != "":
            ids_to_prune, pruned_account_embeds, embed = add_field_to_embed(
                ids_to_prune=ids_to_prune,
                pruned_account_embeds=pruned_account_embeds,
                embed=embed,
                user_id=user_id,
                user=user,
                reason=reason,
            )

            ids_to_prune = ids_to_prune
            pruned_account_embeds = pruned_account_embeds
            embed = embed

        if idx == len(user_ids) - 1:
            pruned_account_embeds.append(embed)

    return ids_to_prune, pruned_account_embeds


async def send_paginated_embed_view(pruned_account_embeds: List[discord.Embed], interaction: discord.Interaction):
    if len(pruned_account_embeds) == 1:
        await interaction.followup.send(embed=pruned_account_embeds[0], wait=True, ephemeral=False)
    else:
        paginated_embed_view = PaginatedEmbedsView(embeds=pruned_account_embeds, timeout=60)

        message: discord.WebhookMessage = await interaction.followup.send(
            embed=pruned_account_embeds[0], view=paginated_embed_view, wait=True, ephemeral=False
        )

        timeout = await paginated_embed_view.wait()

        if timeout:
            await message.edit(view=None)


class PruneAccountsThread(threading.Thread):
    def __init__(
        self,
        duration: int,
        interaction: discord.Interaction,
        client_loop: asyncio.AbstractEventLoop,
        client: discord.Client,
        twitter_client: AsyncClient,
    ):
        threading.Thread.__init__(self)

        self.duration = duration
        self.interaction = interaction
        self.client_loop = client_loop
        self.client = client
        self.twitter_client = twitter_client

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        ids_to_prune, pruned_account_embeds = loop.run_until_complete(
            prune_accounts(duration=self.duration, twitter_client=self.twitter_client)
        )
        loop.close()

        if len(ids_to_prune) == 0:
            asyncio.run_coroutine_threadsafe(self.interaction.delete_original_response(), self.client_loop)
            asyncio.run_coroutine_threadsafe(
                self.interaction.followup.send(content="No accounts were pruned!", ephemeral=True), self.client_loop
            )
            return

        # Set embed footer
        number_of_pages = math.ceil(len(ids_to_prune) / 25)
        for page_num, embed in enumerate(pruned_account_embeds):
            embed.title = "Pruned Accounts"
            embed.description = f"A total of {len(ids_to_prune)} accounts were pruned.\n\nThe pruned Twitter accounts are as follows:\n\u200B"
            embed = set_embed_author(interaction=self.interaction, embed=embed)
            embed.set_footer(text=f"Page {page_num + 1} of {number_of_pages}")

        # Update the Twitter stream user IDs and `IDs.txt`
        ids_to_keep = list(set(TwitterFeed.get_user_ids()).difference(set(ids_to_prune)))
        self.client.twitter_stream.overwrite_ids(user_ids=ids_to_keep)

        asyncio.run_coroutine_threadsafe(self.interaction.delete_original_response(), self.client_loop)
        asyncio.run_coroutine_threadsafe(self.client.twitter_stream.restart(), self.client_loop)
        asyncio.run_coroutine_threadsafe(
            send_paginated_embed_view(pruned_account_embeds=pruned_account_embeds, interaction=self.interaction),
            self.client_loop,
        )
