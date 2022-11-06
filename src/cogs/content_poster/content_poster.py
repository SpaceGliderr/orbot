import math
import os
from datetime import datetime
from typing import List, Literal

import discord
import stringcase
import tweepy
from dateutil import parser
from discord import Permissions, app_commands
from discord.ext import commands

from src.cogs.content_poster.ui.embeds import PostDetailsEmbed
from src.cogs.content_poster.ui.modals import PostChannelModal
from src.cogs.content_poster.ui.views.edit_post import EditPostView
from src.cogs.content_poster.ui.views.post_details import PostChannelView
from src.modules.twitter.feed import TwitterFeed
from src.modules.twitter.twitter import TwitterHelper
from src.modules.ui.custom import PaginatedEmbedsView
from src.orbot import client
from src.utils.config import ContentPosterConfig


class ContentPoster(commands.GroupCog, name="poster"):
    def __init__(self, bot):
        self.bot = bot
        self.twitter_client = tweepy.Client(bearer_token=os.getenv("TWITTER_BEARER_TOKEN"))
        self.account_action_callbacks = {"check": self.check, "follow": self.follow, "unfollow": self.unfollow}

        global global_bot
        global_bot = bot

    # =================================================================================================================
    # COMMAND GROUPS
    # =================================================================================================================
    add_group = app_commands.Group(
        name="add",
        description="Add new elements to the Content Manager auto-post feature.",
        default_permissions=Permissions(manage_messages=True),
        guild_only=True,
    )
    edit_group = app_commands.Group(
        name="edit",
        description="Edit existing elements in the Content Manager auto-post feature.",
        default_permissions=Permissions(manage_messages=True),
        guild_only=True,
    )
    delete_group = app_commands.Group(
        name="delete",
        description="Delete existing elements in the Content Manager auto-post feature.",
        default_permissions=Permissions(manage_messages=True),
        guild_only=True,
    )

    # =================================================================================================================
    # FUNCTIONS
    # =================================================================================================================
    def is_following(self, username: str) -> tuple[bool, str]:
        """A method to check whether a Twitter user with a given username is being followed by comparing the ID received with the IDs in `IDs.txt`.

        Parameters
        ----------
            * username: :class:`str`
                - The username to search for.

        Raises
        ----------
            * Exception
                - If username is not found using Twitter's API.

        Returns
        ----------
            * `tuple[bool, str]`
        """
        user_ids = TwitterFeed.get_user_ids()
        user = self.twitter_client.get_user(username=username)

        if len(user.errors) != 0:
            raise Exception("Can't find username")

        user_id = str(user.data.id)
        return (user_id in user_ids, user_id)

    async def check_account(self, username: str, interaction: discord.Interaction):
        """A wrapper method that calls the `is_following` method. Returns `None` if an Exception is raised, otherwise returns a `tuple[bool, str]`.

        Parameters
        ----------
            * username: :class:`str`
                - The username to search for.
            * interaction: :class:`discord.Interaction`
                - The interaction instance to send a response message.

        Returns
        ----------
            * `tuple[bool, str]` | `None`
        """
        try:
            res = self.is_following(username)
        except:
            await interaction.response.send_message(content="No user found with that username", ephemeral=True)
            return None
        else:
            return res

    async def check(self, interaction: discord.Interaction, username: str):
        """A method that checks the follow status of a Twitter account, responding with an appropriate message.

        Parameters
        ----------
            * username: :class:`str`
                - The username to search for.
            * interaction: :class:`discord.Interaction`
                - The interaction instance to send a response message.
        """
        res = await self.check_account(username, interaction)
        if res is None:
            return

        is_following, _ = res
        await interaction.response.send_message(
            content="This account is already being followed!"
            if is_following
            else "This account is not being followed!",
            ephemeral=True,
        )

    async def follow(self, interaction: discord.Interaction, username: str):
        """A method that adds an account ID from the `IDs.txt` file based on the username provided.

        Parameters
        ----------
            * username: :class:`str`
                - The username to search for and add.
            * interaction: :class:`discord.Interaction`
                - The interaction instance to send a response message.
        """
        res = await self.check_account(username, interaction)
        if res is None:
            return

        is_following, user_id = res
        if not is_following:
            # Write to file
            self.bot.twitter_stream.save_user_id(user_id=user_id, purpose="add")
            # Restart stream
            await self.bot.twitter_stream.restart()
        else:
            await interaction.response.send_message(content="This account is already being followed!", ephemeral=True)

    async def unfollow(self, interaction: discord.Interaction, username: str):
        """A method that removes an account ID from the `IDs.txt` file based on the username provided.

        Parameters
        ----------
            * username: :class:`str`
                - The username to search for and remove.
            * interaction: :class:`discord.Interaction`
                - The interaction instance to send a response message.
        """
        res = await self.check_account(username, interaction)
        if res is None:
            return

        is_following, user_id = res
        if is_following:
            # Remove from file
            self.bot.twitter_stream.save_user_id(user_id=user_id, purpose="remove")
            # Restart stream
            await self.bot.twitter_stream.restart()
        else:
            await interaction.response.send_message(content="This account is not being followed!", ephemeral=True)

    @app_commands.command(name="setup", description="Setup the Twitter feed in a text channel.")
    @app_commands.guild_only()
    @app_commands.describe(channel="the text channel to setup")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def setup(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """A slash command that sets up the Twitter feed in a specified text channel.

        Parameters
        ----------
            * channel: :class:`discord.TextChannel`
                - The text channel that the Twitter feed will be set up in.

        User Flow
        ----------
            * Receives `channel` as the user input
            * Saves the channel ID into the `content_poster.yaml` file

        Permissions
        ----------
        `manage_messages`
        """
        await interaction.response.send_message(
            content=f"The Twitter fansite feed has been successfully setup in <#{channel.id}>"
        )

        cp_conf = ContentPosterConfig()
        data = cp_conf.get_data()
        data["config"]["feed_channel_id"] = channel.id
        cp_conf.dump(data)

        await self.bot.twitter_stream.restart()

    @app_commands.command(
        name="account", description="Either check the follow status of, follow or unfollow a Twitter account."
    )
    @app_commands.guild_only()
    @app_commands.describe(username="the users Twitter handle")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def account(
        self, interaction: discord.Interaction, action: Literal["follow", "unfollow", "check"], username: str
    ):
        """A slash command that either checks the follow status, follows or unfollows a Twitter account.

        Parameters
        ----------
            * action: Literal[`follow`, `unfollow`, `check`]
                - The action to perform on the Twitter account.
            * username: str
                - The Twitter account handle to search.

        Permissions
        ----------
        `manage_messages`
        """
        # TODO: Handle interaction defer properly
        await self.account_action_callbacks[action](interaction, username)

    @add_group.command(name="post-channel", description="Add a posting channel to the Auto-Poster.")
    @app_commands.guild_only()
    @app_commands.describe(channel="the post-able text channel")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def add_post_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """A slash command that adds a post channel to `content_poster.yaml`.

        Parameters
        ----------
            * channel: :class:`discord.TextChannel`
                - The text channel to be added.

        User Flow
        ----------
            * Receives `channel` as the user input
            * Sends user a modal of type `PostChannelModal` then saves user input into the `content_poster.yaml` file

        Permissions
        ----------
        `manage_messages`
        """
        cp_conf = ContentPosterConfig()

        # Send PostChannelModal
        post_channel_modal = PostChannelModal(
            title="Add Post Channel",
            custom_id="add_post_channel_modal",
            timeout=90,
            success_msg="A new post channel was successfully added!",
            error_msg="A few problems were encountered when adding a post channel, please try again!",
            defaults={"id": channel.id, "label": channel.name},
        )

        await interaction.response.send_modal(post_channel_modal)
        timeout = await post_channel_modal.wait()

        if timeout:
            await interaction.followup.send(content="The command has timed out, please try again!", ephemeral=True)
            return

        new_post_channel = post_channel_modal.get_values()
        new_post_channel["id"] = int(new_post_channel["id"])
        new_post_channel["name"] = stringcase.snakecase(str(new_post_channel["label"]))

        data = cp_conf.get_data()
        data["config"]["post_channels"].append(new_post_channel)

        cp_conf.dump(data)

    @edit_group.command(
        name="post-channel", description="Edit details of an existing posting channel in the Auto-Poster."
    )
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_messages=True)
    async def edit_post_channel(self, interaction: discord.Interaction):
        """A slash command that allows users to edit an existing Post Channel.

        User Flow
        ----------
            * Sends a `PostChannelView` to the user
            * Sends user a modal of type `PostChannelModal`
            * Takes user input and updates the post channel in the `content_poster.yaml` file

        Permissions
        ----------
        `manage_messages`
        """
        cp_conf = ContentPosterConfig()

        # Send PostChannelView
        post_channel_view = PostChannelView(timeout=90, stop_view=True)

        await interaction.response.send_message("Select post channel to edit", view=post_channel_view)
        timeout = await post_channel_view.wait()
        await interaction.delete_original_response()

        if timeout:
            await interaction.followup.send(content="The command has timed out, please try again!", ephemeral=True)
            return

        post_channel = post_channel_view.ret_val

        idx, post_channel_details = cp_conf.get_post_channel(post_channel)

        # Send PostChannelModal
        post_channel_modal = PostChannelModal(
            title="Edit Post Channel",
            custom_id="edit_post_channel_modal",
            timeout=90,
            success_msg="The post channel was successfully edited!",
            error_msg="A few problems were encountered when editing the post channel, please try again!",
            defaults=post_channel_details,
        )

        await post_channel_view.interaction.response.send_modal(post_channel_modal)
        timeout = await post_channel_modal.wait()

        if timeout:
            await post_channel_view.interaction.followup.send(
                content="The command has timed out, please try again!", ephemeral=True
            )
            return

        edited_post_channel = post_channel_modal.get_values()
        edited_post_channel["name"] = stringcase.snakecase(
            str(edited_post_channel["label"])
        )  # Generates a snakecased `name` attribute from the label
        edited_post_channel["id"] = int(edited_post_channel["id"])

        data = cp_conf.get_data()
        data["config"]["post_channels"][idx] = {
            **data["config"]["post_channels"][idx],
            **edited_post_channel,
        }

        cp_conf.dump(data)

    @delete_group.command(name="post-channel", description="Delete an existing posting channel in the Auto-Poster.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_messages=True)
    async def delete_post_channel(self, interaction: discord.Interaction):
        """A slash command that allows users to delete an existing Post Channel.

        User Flow
        ----------
            * Sends a `PostChannelView` to the user
            * Sends user a modal of type `PostChannelModal`
            * Takes user input and updates the post channel in the `content_poster.yaml` file

        Permissions
        ----------
        `manage_messages`
        """
        cp_conf = ContentPosterConfig()

        # Send PostChannelView
        post_channel_view = PostChannelView(timeout=90, stop_view=True)

        await interaction.response.send_message("Select post channel to edit", view=post_channel_view)
        timeout = await post_channel_view.wait()
        await interaction.delete_original_response()

        if timeout:
            await interaction.followup.send(content="The command has timed out, please try again!", ephemeral=True)
            return

        post_channel = post_channel_view.ret_val
        data = cp_conf.get_data()
        idx, _ = cp_conf.get_post_channel(post_channel)
        del data["config"]["post_channels"][idx]

        cp_conf.dump(data)

    @client.tree.context_menu(name="Edit Post")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_messages=True)
    async def edit_post(interaction: discord.Interaction, message: discord.Message):
        """A context menu command that allows users to edit an existing Post made in a Post Channel.

        User Flow
        ----------
            * Sends an `EditPostView` to the user in the feed channel

        Permissions
        ----------
        `manage_messages`
        """
        cp_conf = ContentPosterConfig()
        feed_channel = await message.channel.guild.fetch_channel(cp_conf.data["config"]["feed_channel_id"])
        await interaction.response.send_message(content=f"Edit this post in <#{feed_channel.id}>", ephemeral=True)

        files = [await attachment.to_file() for attachment in message.attachments]
        post_details = {
            "message": message,
            "caption": message.content,
            "caption_credits": ContentPosterConfig.anatomize_post_caption(message.content),
            "files": files.copy(),
            "channels": [str(interaction.channel.id)],
        }

        post_details_embed = PostDetailsEmbed(post_details=post_details)
        post_details_embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.avatar)
        embedded_message = await feed_channel.send(embed=post_details_embed)
        view = EditPostView(
            post_details=post_details,
            embedded_message=embedded_message,
            bot=global_bot,
            files=files,
            interaction_user=interaction.user,
        )
        await embedded_message.edit(view=view)

        await view.wait()
        await embedded_message.edit(view=None)

    @app_commands.command(name="create-post", description="Makes a new post with a given Tweet link")
    @app_commands.guild_only()
    @app_commands.rename(tweet_type="type", tweet_link="link")
    @app_commands.describe(tweet_type="type of Tweet", tweet_link="the Tweet link(s)")
    @app_commands.choices(
        tweet_type=[
            app_commands.Choice(
                name="Recent (posted less than 7 days ago, enter only the parent tweet link)", value="recent"
            ),
            app_commands.Choice(name="Any (enter all tweet links separated with a comma)", value="any"),
        ]
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def create_post(
        self, interaction: discord.Interaction, tweet_type: app_commands.Choice[str], tweet_link: str
    ):
        """A slash command that allows users to create a post by providing link(s) to Tweet(s).

        Parameters
        ----------
            * tweet_type: :class:`discord.TextChannel`
                - The text channel that the Role Picker will be set up in
            * tweet_link: :class:`discord.TextChannel`
                - The text channel that the Role Picker will be set up in

        User Flow
        ----------
            * Retrieves Tweet(s) using the Twitter Client
            * Sorts the media obtained from the Tweet(s)
            * Sends a message with a `PersistentTweetView` to the feed channel

        Permissions
        ----------
        `manage_messages`
        """
        await interaction.response.defer(ephemeral=True)

        channel = ContentPosterConfig().get_feed_channel(self.bot)

        ids_chronological_order = []

        if tweet_type.value == "recent":  # Will only have one tweet link
            # Split and obtain the API parameters from the Tweet link
            split_link = tweet_link.split("/")
            username = split_link[3]
            tweet_id = split_link[-1]

            # Get the recent tweets using the Twitter API (only need the Tweet IDs)
            recent_tweets = self.twitter_client.search_recent_tweets(
                query=f'(url:"{tweet_link}" OR conversation_id:{tweet_id}) from:{username} has:media'
            )

            if recent_tweets.data is None:
                await interaction.followup.send(
                    content="The tweet you tried to search cannot be found or was posted more than 7 days ago. Please use the `any` tweet type and provide all relevant Tweet links separated by commas.",
                    ephemeral=True,
                )
                return

            # Reverse the order for the Tweet IDs
            ids_chronological_order = list(reversed([tweet["id"] for tweet in recent_tweets.data]))
        else:  # Will only have multiple tweet links
            # Split and obtain the ids from the Tweet links
            links = tweet_link.split(",")
            ids_chronological_order = [link.strip().split("/")[-1] for link in links]

        # Get all the relevant Tweets using the Twitter API (returns all tweet information)
        tweets = self.twitter_client.get_tweets(
            ids=ids_chronological_order,
            tweet_fields=["attachments", "conversation_id", "entities"],
            media_fields=["url", "variants"],
            user_fields=["name", "username"],
            expansions=["attachments.media_keys", "author_id"],
        )

        # Extract relevant tweet information and send the post to the feed channel
        urls_per_post, filenames_per_post, metadata = await TwitterHelper.parse_response_object(tweets)

        for idx, post_urls in enumerate(urls_per_post):
            await TwitterHelper.send_post(
                urls=post_urls, media_filenames=filenames_per_post[idx], client=self.bot, channel=channel, **metadata
            )

        await interaction.followup.send(content=f"Tweet successfully created in <#{channel.id}>", ephemeral=True)

    @app_commands.command(
        name="prune-accounts", description="Removes Twitter accounts which have been inactive for a period of time"
    )
    @app_commands.guild_only()
    @app_commands.describe(duration="period of inactivity (in days)")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def prune_accounts(self, interaction: discord.Interaction, duration: int):
        """A slash command that allows users to prune Twitter IDs older than a user provided duration in days.

        It is an expensive operation, do not run this more than a few times a month, due to Twitter APIs Tweet reading limitation (2 million Tweets can be read a month).

        Parameters
        ----------
            * days: :class:`int`
                - Prune threshold of account inactivity in days.

        User Flow
        ----------
            * Gets the list of Twitter user IDs separated by commas
            * For each user ID, it retrieves the 5 most recent Tweets of the user
            * Using the most recent tweet, it checks the time of posting with the present date
                - If the date is more than the threshold, it is pruned from the `IDs.txt` file
            * Finally, it restarts the Twitter stream to apply the updated user IDs

        Permissions
        ----------
        `manage_messages`
        """
        await interaction.response.defer(ephemeral=True)

        user_ids = TwitterFeed.get_user_ids()
        ids_to_prune = []
        pruned_account_embeds = []

        embed = discord.Embed(
            title="Pruned Accounts", description="Shows the Twitter accounts that were pruned:\n\u200B"
        )

        def add_field_to_embed(
            ids_to_prune: List[int],
            pruned_account_embeds: List[discord.Embed],
            embed: discord.Embed,
            user_id: int,
            user: dict,
            reason: str,
        ):
            ids_to_prune.append(user_id)

            embed.add_field(
                name=f"{user['name']} @{user['username']}" if user is not None else user_id, value=reason, inline=False
            )

            if len(ids_to_prune) % 25 == 0:
                pruned_account_embeds.append(embed)
                embed.clear_fields()

            return ids_to_prune, pruned_account_embeds, embed

        for user_id in user_ids:
            # Get the 5 most recent tweets from a given user ID
            result = self.twitter_client.get_users_tweets(
                id=user_id, max_results=5, tweet_fields=["created_at"], expansions="author_id"
            )
            # Get the user information of the user ID
            # Cannot obtain user information from `get_users_tweets` as in the case when a user has not posted any tweets,
            # `get_users_tweets` will return an empty object for the user even though the user exists
            user_response = client.get_user(id=user_id, user_fields=["name", "username"])

            # Get user object
            user = None
            if user_response.data is not None:
                user = user_response.data.data

            if user is None:  # If user can't be found, means it is deleted or does not exist
                ids_to_prune, pruned_account_embeds, embed = add_field_to_embed(
                    ids_to_prune=ids_to_prune,
                    pruned_account_embeds=pruned_account_embeds,
                    embed=embed,
                    user_id=user_id,
                    user=user,
                    reason="_<Account deleted or does not exist>_",
                )
            elif (
                len(result.errors) != 0
            ):  # If there is an error, it means that the account is protected and the tweets cannot be accessed
                ids_to_prune, pruned_account_embeds, embed = add_field_to_embed(
                    ids_to_prune=ids_to_prune,
                    pruned_account_embeds=pruned_account_embeds,
                    embed=embed,
                    user_id=user_id,
                    user=user,
                    reason="_<Account privated>_",
                )
            else:
                try:
                    # Access the most recent tweet
                    recent_tweet_date = parser.parse(result.data[0].data["created_at"]).date()
                    date_diff = datetime.now().date() - recent_tweet_date  # Find duration of the last post

                    if (
                        date_diff.days > duration
                    ):  # Check whether the days since the last post exceeds specified duration threshold
                        ids_to_prune, pruned_account_embeds, embed = add_field_to_embed(
                            ids_to_prune=ids_to_prune,
                            pruned_account_embeds=pruned_account_embeds,
                            embed=embed,
                            user_id=user_id,
                            user=user,
                            reason=f"_Last Tweet on {recent_tweet_date}, {date_diff} days ago_",
                        )
                except:  # Handles error thrown by accessing an empty object (no tweets available)
                    ids_to_prune, pruned_account_embeds, embed = add_field_to_embed(
                        ids_to_prune=ids_to_prune,
                        pruned_account_embeds=pruned_account_embeds,
                        embed=embed,
                        user_id=user_id,
                        user=user,
                        reason="_<Account has no Tweets>_",
                    )

        if len(ids_to_prune) == 0:
            await interaction.followup.send(content="No accounts were pruned!", ephemeral=True)
            return

        # Set embed footer
        number_of_pages = math.ceil(len(ids_to_prune) / 25)
        for page_num, embed in enumerate(pruned_account_embeds):
            embed.set_footer(text=f"Page {page_num + 1} of {number_of_pages}")

        # Update the Twitter stream user IDs and `IDs.txt`
        ids_to_keep = list(set(user_ids).difference(set(ids_to_prune)))
        self.bot.twitter_stream.overwrite_ids(user_ids=ids_to_keep)

        await interaction.followup.send(
            embed=pruned_account_embeds[0],
            view=PaginatedEmbedsView(embeds=pruned_account_embeds) if len(pruned_account_embeds) != 1 else None,
        )

    @edit_group.command(
        name="hashtag-filters",
        description="Updates the whitelisted and blacklisted hashtags to filter incoming Tweets",
    )
    @app_commands.guild_only()
    @app_commands.rename(list_type="list")
    @app_commands.describe(
        list_type="type of list",
        action="action to perform on the list",
        hashtags="hashtags to add to the specified list (separated by commas)",
    )
    @app_commands.choices(
        list_type=[
            app_commands.Choice(name="blacklist", value="blacklist"),
            app_commands.Choice(name="whitelist", value="whitelist"),
        ],
        action=[
            app_commands.Choice(name="add hashtags", value="add"),
            app_commands.Choice(name="remove hashtags", value="remove"),
        ],
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def edit_hashtag_filters(
        self,
        interaction: discord.Interaction,
        list_type: app_commands.Choice[str],
        action: app_commands.Choice[str],
        hashtags: str,
    ):
        """A slash command that allows users to edit the hashtag filter whitelist and blacklist of the Twitter feed.

        Parameters
        ----------
            * interaction: :class:`discord.Interaction`
                - Prune threshold of account inactivity in days.
            * list_type: :class:`app_commands.Choice[str]`
                - Chooses the type of hashtag filter list to edit.
            * action: :class:`app_commands.Choice[str]`
                - Chooses whether to add or remove hashtags from the selected list.
            * hashtag: :class:`str`
                - The list of hashtags to add/remove, separated by commas.

        User Flow
        ----------
            * Gets the list of hashtags separated by commas.
            * Then, it adds/removes the list of hashtags from the whitelist/blacklist.
            * Finally, it saves the hashtags into the config file and sends an embed to show the user what has been added/removed.

        Permissions
        ----------
        `manage_messages`
        """
        await interaction.response.defer(ephemeral=True)

        hashtag_list = hashtags.split(",")  # Obtain hashtags

        cp_conf = ContentPosterConfig()
        data = cp_conf.get_data()
        current_hashtag_list = cp_conf.hashtag_filters[list_type.value]

        success = []  # Stores the hashtags that were successfully added/removed
        neutral = []  # Stores the hashtags that were not added/removed

        for h in hashtag_list:
            hashtag = h.strip()

            if action.value == "add":
                if hashtag in current_hashtag_list:
                    neutral.append(hashtag)
                else:
                    data["config"]["hashtag_filters"][list_type.value].append(hashtag)
                    success.append(hashtag)
            else:
                if hashtag not in current_hashtag_list:
                    neutral.append(hashtag)
                else:
                    data["config"]["hashtag_filters"][list_type.value].remove(hashtag)
                    success.append(hashtag)

        cp_conf.dump(data)  # Save data to config file

        # Send embed to user to show the user what was/wasn't added/removed
        verb = f"{action.value}ed" if action.value == "add" else f"{action.value}d"

        embed = discord.Embed(title=f"Added to {list_type.value.capitalize()}", description="\n\u200B")
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.avatar)
        embed.add_field(
            name=f"Successfully {verb.capitalize()}",
            value=f"#{', #'.join(success)}\n\u200B" if len(success) != 0 else f"_No hashtags were {verb}_",
            inline=False,
        )
        embed.add_field(
            name="Already Exists" if action.value == "add" else "Does Not Exist",
            value=f"#{', #'.join(neutral)}" if len(neutral) != 0 else f"_All hashtags were successfully {verb}_",
            inline=False,
        )

        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(
        name="view-hashtag-filters",
        description="View the whitelisted and blacklisted hashtags that filters incoming Tweets",
    )
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_messages=True)
    async def view_hashtag_filters(self, interaction: discord.Interaction):
        """A slash command that sends the user an embed with all the whitelisted and blacklisted hashtags.

        Permissions
        ----------
        `manage_messages`
        """
        hashtag_filters = ContentPosterConfig().hashtag_filters

        embed = discord.Embed(
            title="Hashtag Filters",
            description="The list of hashtags used to filter incoming Tweets on the feed\n\u200B",
        )
        embed.add_field(
            name="Whitelisted Hashtags",
            value=f'{", ".join(hashtag_filters["whitelist"])}\n\u200B'
            if len(hashtag_filters["whitelist"]) != 0
            else "_No whitelisted hashtags_\n\u200B",
            inline=False,
        )
        embed.add_field(
            name="Blacklisted Hashtags",
            value=f'{", ".join(hashtag_filters["blacklist"])}'
            if len(hashtag_filters["blacklist"]) != 0
            else "_No blacklisted hashtags_",
            inline=False,
        )

        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(ContentPoster(bot))
