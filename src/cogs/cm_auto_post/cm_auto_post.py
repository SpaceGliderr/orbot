from os import walk
import discord
from discord import Permissions, app_commands
from discord.ext import commands
from src.cogs.cm_auto_post.ui import PostChannelModal, PostChannelView

from src.utils.config import CMAutoPostConfig

import stringcase


class CMAutoPost(commands.GroupCog, name="cm-post"):
    def __init__(self, bot):
        self.bot = bot
    

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

    
    @app_commands.command(name="mock-post", description="Sends a mock post to the channel provided by the setup.")
    @app_commands.guild_only()
    async def mock_post(self, interaction: discord.Interaction):
        """Mocks an incoming Twitter post"""
        files = [discord.File(fp=f"loonatheworld/{filename}", filename=filename) for filename in next(walk("loonatheworld"), (None, [], []))[2]]

        cmap_conf = CMAutoPostConfig()

        await interaction.response.send_message("Mock Post created", ephemeral=True)

        channel = await interaction.guild.fetch_channel(cmap_conf.data["config"]["feed_channel_id"])
        await channel.send(content="@loonatheworld", files=files)


    
    @app_commands.command(name="setup-feed", description="Setup the Twitter feed in a text channel.")
    @app_commands.guild_only()
    @app_commands.describe(channel="the text channel to setup in")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def setup_feed(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await interaction.response.send_message(content=f"The Twitter fansite feed has been successfully setup in <#{channel.id}>")

        cmap_conf = CMAutoPostConfig()
        data = cmap_conf.get_data()
        data["config"]["feed_channel_id"] = channel.id
        cmap_conf.dump(data)


    @app_commands.command(name="follow", description="Follow a Twitter account.")
    @app_commands.guild_only()
    @app_commands.describe(handle="the users Twitter handle")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def follow(self, interaction: discord.Interaction, handle: str):
        pass


    @app_commands.command(name="unfollow", description="Unfollow a Twitter account.")
    @app_commands.guild_only()
    @app_commands.describe(handle="the users Twitter handle")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def unfollow(self, interaction: discord.Interaction, handle: str):
        pass


    @app_commands.command(name="check", description="Check whether a Twitter account is being followed.")
    @app_commands.guild_only()
    @app_commands.describe(handle="the users Twitter handle")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def check(self, interaction: discord.Interaction, handle: str):
        pass

    
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
            defaults={ "id": channel.id, "label": channel.name }
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


    @edit_group.command(name="post-channel", description="Edit details of an existing posting channel in the Auto-Poster.")
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
            defaults=post_channel_details
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


    @edit_group.command(name="post", description="Edit a post sent by the Auto-Poster.")
    @app_commands.guild_only()
    @app_commands.describe(message="the message posted by the bot")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def edit_post(self, interaction: discord.Interaction, message: str):
        pass


async def setup(bot):
    await bot.add_cog(CMAutoPost(bot))
