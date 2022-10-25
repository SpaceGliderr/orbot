import os
from typing import Literal

import discord
import stringcase
import tweepy
from discord import Permissions, app_commands
from discord.ext import commands

from src.cogs.content_poster.ui import (
    EditPostView,
    PostChannelModal,
    PostChannelView,
    PostDetailsEmbed,
)
from src.modules.twitter.feed import TwitterFeed
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
            await interaction.response.send_message(content="No user found with that username")
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
        if is_following:
            await interaction.response.send_message(content="This account is already being followed!")
        else:
            await interaction.response.send_message(content="This account is not being followed!")

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
            await interaction.response.send_message(content="This account is already being followed!")

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
            await interaction.response.send_message(content="This account is not being followed!")

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

        # TODO: Setup or refresh function if a stream is running

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


async def setup(bot):
    await bot.add_cog(ContentPoster(bot))
