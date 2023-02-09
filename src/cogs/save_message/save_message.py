import discord
from discord import app_commands
from discord.ext import commands

from src.cogs.save_message.view import SaveMessageEmbed
from src.orbot import client


async def send_save_message_dm(interaction: discord.Interaction, message: discord.Message):
    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=True)

    dm_channel = await client.create_dm(interaction.user)
    dm = await dm_channel.send(
        content=f"💬 Message by **{message.author.name}#{message.author.discriminator}** saved",
        embed=SaveMessageEmbed(message=message, color=message.author.color),
    )

    await interaction.edit_original_response(content=f"You have successfully saved a message!\n{dm.jump_url}")


@client.tree.context_menu(name="Save Message")
@app_commands.guild_only()
async def save_message(interaction: discord.Interaction, message: discord.Message):
    await send_save_message_dm(interaction=interaction, message=message)


class SaveMessage(commands.GroupCog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="save-message", description="Saves a Discord message in your DMs")
    @app_commands.guild_only()
    @app_commands.describe(message_link="the link to the message to save")
    async def save_message(self, interaction: discord.Interaction, message_link: str):
        await interaction.response.defer(ephemeral=True)

        # 1. Get guild ID and channel ID from message link
        guild_id = message_link.split("/")[3]
        channel_id = message_link.split("/")[4]
        message_id = message_link.split("/")[5]

        # 2. Fetch channel
        guild = await self.bot.fetch_guild(guild_id)
        channel = await guild.fetch_channel(channel_id)
        message = await channel.fetch_message(message_id)

        # 3. Generate embed and send DM
        await send_save_message_dm(interaction=interaction, message=message)


async def setup(bot):
    await bot.add_cog(SaveMessage(bot))
