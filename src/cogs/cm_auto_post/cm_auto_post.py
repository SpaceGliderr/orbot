import discord
from discord import Permissions, app_commands
from discord.ext import commands

from utils.config import CMAutoPostConfig


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
        # TODO: Create a folder with multiple images, when command is called, send the folder as a tweet
        pass

    
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
    async def follow(self, handle: str):
        pass


    @app_commands.command(name="unfollow", description="Unfollow a Twitter account.")
    @app_commands.guild_only()
    @app_commands.describe(handle="the users Twitter handle")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def unfollow(self, handle: str):
        pass


    @app_commands.command(name="check", description="Check whether a Twitter account is being followed.")
    @app_commands.guild_only()
    @app_commands.describe(handle="the users Twitter handle")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def check(self, handle: str):
        pass

    
    @add_group.command(name="post-channel", description="Add a posting channel to the Auto-Poster.")
    @app_commands.guild_only()
    @app_commands.describe(channel="the post-able text channel")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def add_post_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        pass


    @edit_group.command(name="post-channel", description="Edit details of an existing posting channel in the Auto-Poster.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_messages=True)
    async def edit_post_channel(self):
        pass


    @delete_group.command(name="post-channel", description="Delete an existing posting channel in the Auto-Poster.")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_messages=True)
    async def delete_post_channel(self):
        pass


    @edit_group.command(name="post", description="Edit a post sent by the Auto-Poster.")
    @app_commands.guild_only()
    @app_commands.describe(message="the message posted by the bot")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def edit_post(self, message: discord.Message):
        pass


async def setup(bot):
    await bot.add_cog(CMAutoPost(bot))
