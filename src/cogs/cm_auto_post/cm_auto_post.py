import os
from typing import Literal

import discord
import stringcase
import tweepy
from discord import Permissions, app_commands
from discord.ext import commands

from src.cogs.cm_auto_post.ui import (
    EditPostEmbed,
    EditPostView,
    PostChannelModal,
    PostChannelView,
)
from src.orbot import client
from src.utils.config import CMAutoPostConfig


class CMAutoPost(commands.GroupCog, name="cm-post"):
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

    def is_following(self, username: str) -> tuple[bool, str]:
        user_ids = CMAutoPostConfig.get_user_ids()
        user = self.twitter_client.get_user(username=username)

        if len(user.errors) != 0:
            raise Exception("Can't find username")

        user_id = str(user.data.id)
        return (user_id in user_ids, user_id)

    async def _check(self, interaction: discord.Interaction, username: str):
        try:
            res = self.is_following(username)
        except:
            await interaction.response.send_message(content="No user found with that username")
            return None
        else:
            return res

    async def check(self, interaction: discord.Interaction, username: str):
        res = await self._check(interaction, username)
        if res is None:
            return

        is_following, _ = res
        if is_following:
            await interaction.response.send_message(content="This account is already being followed!")
        else:
            await interaction.response.send_message(content="This account is not being followed!")

    async def follow(self, interaction: discord.Interaction, username: str):
        res = await self._check(interaction, username)
        if res is None:
            return

        is_following, user_id = res
        if not is_following:
            # Write to file
            self.bot.twitter_stream.save_user_id(purpose="add", user_id=user_id)
            # Restart stream
            await self.bot.twitter_stream.restart_stream()
        else:
            await interaction.response.send_message(content="This account is already being followed!")

    async def unfollow(self, interaction: discord.Interaction, username: str):
        res = await self._check(interaction, username)
        if res is None:
            return

        is_following, user_id = res
        if is_following:
            # Remove from file
            self.bot.twitter_stream.save_user_id(purpose="remove", user_id=user_id)
            # Restart stream
            await self.bot.twitter_stream.restart_stream()
        else:
            await interaction.response.send_message(content="This account is not being followed!")

    @app_commands.command(name="setup-feed", description="Setup the Twitter feed in a text channel.")
    @app_commands.guild_only()
    @app_commands.describe(channel="the text channel to setup in")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def setup_feed(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await interaction.response.send_message(
            content=f"The Twitter fansite feed has been successfully setup in <#{channel.id}>"
        )

        cmap_conf = CMAutoPostConfig()
        data = cmap_conf.get_data()
        data["config"]["feed_channel_id"] = channel.id
        cmap_conf.dump(data)

    @app_commands.command(name="account", description="Check whether a Twitter account is being followed.")
    @app_commands.guild_only()
    @app_commands.describe(username="the users Twitter handle")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def account(
        self, interaction: discord.Interaction, action: Literal["follow", "unfollow", "check"], username: str
    ):
        # TODO: Handle interaction defer properly
        await self.account_action_callbacks[action](interaction, username)

    @add_group.command(name="post-channel", description="Add a posting channel to the Auto-Poster.")
    @app_commands.guild_only()
    @app_commands.describe(channel="the post-able text channel")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def add_post_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        cmap_conf = CMAutoPostConfig()

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

        data = cmap_conf.get_data()
        data["config"]["post_channels"].append(new_post_channel)

        cmap_conf.dump(data)

    @edit_group.command(
        name="post-channel", description="Edit details of an existing posting channel in the Auto-Poster."
    )
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_messages=True)
    async def edit_post_channel(self, interaction: discord.Interaction):
        cmap_conf = CMAutoPostConfig()

        # Send PostChannelView
        post_channel_view = PostChannelView(timeout=90, stop_view=True)

        await interaction.response.send_message("Select post channel to edit", view=post_channel_view)
        timeout = await post_channel_view.wait()
        await interaction.delete_original_response()

        if timeout:
            await interaction.followup.send(content="The command has timed out, please try again!", ephemeral=True)
            return

        post_channel = post_channel_view.values

        idx, post_channel_details = cmap_conf.get_post_channel(post_channel)

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

        data = cmap_conf.get_data()
        data["config"]["post_channels"][idx] = {
            **data["config"]["post_channels"][idx],
            **edited_post_channel,
        }

        cmap_conf.dump(data)

    @delete_group.command(name="post-channel", description="Delete an existing posting channel in the Auto-Poster.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_messages=True)
    async def delete_post_channel(self, interaction: discord.Interaction):
        cmap_conf = CMAutoPostConfig()

        # Send PostChannelView
        post_channel_view = PostChannelView(timeout=90, stop_view=True)

        await interaction.response.send_message("Select post channel to edit", view=post_channel_view)
        timeout = await post_channel_view.wait()
        await interaction.delete_original_response()

        if timeout:
            await interaction.followup.send(content="The command has timed out, please try again!", ephemeral=True)
            return

        post_channel = post_channel_view.values
        data = cmap_conf.get_data()
        idx, _ = cmap_conf.get_post_channel(post_channel)
        del data["config"]["post_channels"][idx]

        cmap_conf.dump(data)

    @client.tree.context_menu(name="Edit Post")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_messages=True)
    async def edit_post_ctx_menu(interaction: discord.Interaction, message: discord.Message):
        cmap_conf = CMAutoPostConfig()
        feed_channel = await message.channel.guild.fetch_channel(cmap_conf.data["config"]["feed_channel_id"])
        await interaction.response.send_message(content=f"Edit this post in <#{feed_channel.id}>", ephemeral=True)

        files = [await attachment.to_file() for attachment in message.attachments]
        post_details = {
            "message": message,
            "caption": message.content,
            "caption_credits": CMAutoPostConfig.anatomize_post_caption(message.content),
            "files": files,
        }

        embedded_message = await feed_channel.send(embed=EditPostEmbed(post_details))
        view = EditPostView(post_details=post_details, embedded_message=embedded_message, bot=global_bot)
        await embedded_message.edit(view=view)

        await view.wait()
        await embedded_message.edit(view=None)

        if view.is_confirmed:
            await view.interaction.followup.send(
                content=f"The post was successfully edited in <#{message.channel.id}>. {message.jump_url}"
            )


async def setup(bot):
    await bot.add_cog(CMAutoPost(bot))
