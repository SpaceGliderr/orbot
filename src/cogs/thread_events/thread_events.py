import asyncio
import re
from typing import Literal, Union

import discord
import emoji
from discord import app_commands
from discord.ext import commands

from src.cogs.thread_events.view import (
    ChannelEventDetailsEmbed,
    EditChannelEventDetailsView,
    ReplaceReactEmojiView,
)
from src.utils.config import ThreadEventsConfig
from src.utils.helper import send_or_edit_interaction_message


class ThreadEvents(commands.GroupCog, name="thread-event"):
    def __init__(self, bot):
        self.bot = bot

    # =================================================================================================================
    # FUNCTIONS
    # =================================================================================================================
    async def get_emojis_from_string(self, string: str, guild: discord.Guild):
        """Converts a list of `discord.File`s to a ZIP file.

        Parameters
        ----------
            * string: :class:`string`
                - The string of emojis.
            * guild: :class:`discord.Guild`
                - The guild where the custom Discord emojis should originate from.
        """
        # The following line encodes the string in `unicode-escape` codec to convert all unicode strings into unicode characters
        # Then, the decode `ASCII` codec is used to convert the unicode characters into ASCII symbols (normal processable characters)
        # Finally, use the split function to split the string based on the comma character to get all emoji strings
        emoji_strs = string.encode("unicode-escape").decode("ASCII").split(",")

        emojis = []  # Stores emoji strings if it's a default emoji OR emoji ID if it's a custom Discord emoji

        for emoji_str in emoji_strs:
            emoji_str = emoji_str.strip()  # Remove whitespace
            custom_emoji_id_match = re.search(r"\:\d+\>", emoji_str)  # For extracting the ID from custom Discord emojis

            # Check if a match exists. There can be strings without any matches (which is considered a default emoji or an invalid one)
            if custom_emoji_id_match:
                try:
                    custom_emoji_id = int(custom_emoji_id_match.group()[1:-1])
                    await guild.fetch_emoji(
                        custom_emoji_id
                    )  # Check whether the custom Discord emoji belongs to the current guild
                    emojis.append(custom_emoji_id)
                except:
                    raise Exception("One of the emojis provided does not belong to the current guild.")
            else:
                # Need to encode ASCII and decode `unicode-escape` again to obtain the emoji itself
                # Directly storing the emoji as unicode makes it easier for the bot to react when an event is fired
                # No need to `fetch_emoji` as it is already stored in emoji format
                ori_emoji_str = emoji_str.encode("ASCII").decode("unicode-escape")
                if emoji.is_emoji(
                    ori_emoji_str
                ):  # Check whether the emoji is a valid default emoji using the `emoji` library
                    emojis.append(ori_emoji_str)
                else:
                    raise Exception("One of the emojis provided is not an emote.")

        return emojis

    async def add_reactions_to_thread(
        self, thread: discord.Thread, event_type: Literal["on_thread_create", "on_thread_update"]
    ):
        """A method that adds channel event emojis from the `thread_events.yaml` file as reactions to the thread or forum post.

        Parameters
        ----------
            * thread: :class:`discord.Thread`
            * event_type: :class:`Literal["on_thread_create", "on_thread_update"]`
        """
        # Get threads first message
        #  - Cannot use thread.starter_message as that fetches the starter message from the cache
        #  - On creation, the cache would not have updated to give the `starter_message` property
        #  - Therefore, since the threads ID is the same as the starter messages ID, use `fetch_message` to get the Message object
        starter_message = await thread.fetch_message(thread.id)

        # Edit the message with the appropriate reactions
        event = ThreadEventsConfig().get_channel_event(event=event_type, channel_id=thread.parent_id)

        if event:
            # If the `react_emoji` is an integer type, it means that it is a custom Discord emoji
            # - Therefore, we need to use the `thread.guild` to fetch the emoji and then only react
            # - That's why the react emojis cannot be from a different guild that the channel is located in, otherwise the bot would not be able to grab the emoji
            if event["ordered"]:
                # The following logic ensures that the reactions are added in the specific order by going through the list and waiting for each individual reaction to be added
                # This will be slower in terms of execution speed
                for react_emoji in event["react_emojis"]:
                    await starter_message.add_reaction(
                        await thread.guild.fetch_emoji(react_emoji) if isinstance(react_emoji, int) else react_emoji
                    )
            else:
                # The following logic uses the `gather` function to add the reacts in parallel, there will be a chance that the reacts appear out of the order it is stored
                await asyncio.gather(
                    *[
                        starter_message.add_reaction(
                            await thread.guild.fetch_emoji(react_emoji) if isinstance(react_emoji, int) else react_emoji
                        )
                        for react_emoji in event["react_emojis"]
                    ]
                )

    # =================================================================================================================
    # GENERAL SLASH COMMANDS
    # =================================================================================================================
    @app_commands.command(
        name="create-thread-reaction-event",
        description="Automatically adds reactions when a thread or forum post is created or updated.",
    )
    @app_commands.guild_only()
    @app_commands.rename(emoji_str="react_emojis")
    @app_commands.choices(
        event=[
            app_commands.Choice(
                name="when a thread or forum post is created",
                value="on_thread_create",
            ),
            app_commands.Choice(name="when a thread or forum post is updated", value="on_thread_update"),
        ],
        ordered=[
            app_commands.Choice(name="the reactions will follow the specific order specified on input", value=1),
            app_commands.Choice(name="the reactions might appear in a different order compared to on input", value=0),
        ],
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def create_thread_reaction_event(
        self,
        interaction: discord.Interaction,
        event: app_commands.Choice[str],
        channel: Union[discord.TextChannel, discord.ForumChannel],
        ordered: app_commands.Choice[int],
        emoji_str: str,
    ):
        """A slash command that allows the user to create a thread or forum event that adds reactions to the original thread message.

        Parameters
        ----------
            * interaction: :class:`discord.Interaction`
            * event: app_commands.Choice[:class:`str`]
                - The type of thread or forum event that would be responded to. Reactions will be added either when the thread is created or when the thread is updated.
            * channel: Union[:class:`discord.TextChannel`, :class:`discord.ForumChannel`]
                - Channel to listen to for the event.
            * ordered: app_commands.Choice[:class:`int`]
                - Whether the emojis will be in the order it is entered in the `emoji_str` or not.
            * emoji_str: :class:`str`
                - The emojis to react to the thread with.
        """
        te_conf = ThreadEventsConfig()

        replace_react_emoji_view = None

        if te_conf.get_channel_event(
            event=event.value, channel_id=channel.id
        ):  # Check whether a corresponding channel event already exists or not
            # Send a message to confirm whether the user wants to replace reactions or add them onto the current reactions
            replace_react_emoji_view = ReplaceReactEmojiView(timeout=180)
            await interaction.response.send_message(
                view=replace_react_emoji_view,
                embed=discord.Embed(
                    title="Channel Event Exists",
                    description="The specific channel event already exists. Would you like to add the reactions or replace the reactions?",
                ),
                ephemeral=True,
            )

            # Handle timeout
            timeout = await replace_react_emoji_view.wait()
            if timeout or replace_react_emoji_view.is_cancelled:
                return await interaction.edit_original_response(
                    content="The command has timed out. Please try again."
                    if timeout
                    else "Command cancelled. No reactions were added to the existing channel event.",
                    view=None,
                    embed=None,
                )

        try:
            emojis = await self.get_emojis_from_string(string=emoji_str, guild=interaction.guild)
            te_conf.upsert_channel_event(
                event=event.value,
                channel_id=channel.id,
                ordered=True if ordered.value == 1 else False,
                react_emojis=emojis,
                replace_reactions=replace_react_emoji_view.replace if replace_react_emoji_view else True,
            )

            await send_or_edit_interaction_message(
                interaction=interaction,
                edit_original_response=True,
                content="Successfully added channel event.",
                view=None,
                embed=None,
                ephemeral=True,
            )
        except Exception as e:
            await send_or_edit_interaction_message(
                interaction=interaction,
                edit_original_response=True,
                content=str(e),
                view=None,
                embed=None,
                ephemeral=True,
            )

    @app_commands.command(
        name="edit-thread-reaction-event",
        description="Edit reactions that are added to a thread or forum post on create or update.",
    )
    @app_commands.guild_only()
    @app_commands.choices(
        event=[
            app_commands.Choice(
                name="when a thread or forum post is created",
                value="on_thread_create",
            ),
            app_commands.Choice(name="when a thread or forum post is updated", value="on_thread_update"),
        ],
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def edit_thread_reaction_event(
        self,
        interaction: discord.Interaction,
        event: app_commands.Choice[str],
        channel: Union[discord.TextChannel, discord.ForumChannel],
    ):
        """A slash command that allows the user to create a thread or forum event that adds reactions to the original thread message.

        Parameters
        ----------
            * interaction: :class:`discord.Interaction`
            * event: app_commands.Choice[:class:`str`]
                - The type of thread or forum event to search for.
            * channel: Union[:class:`discord.TextChannel`, :class:`discord.ForumChannel`]
                - The channel of the thread or forum event to search for.
        """
        te_conf = ThreadEventsConfig()
        channel_event = te_conf.get_channel_event(event=event.value, channel_id=channel.id)

        if channel_event:
            # Obtain all emojis from the `react_emojis` key from the `channel_event` variable and find their corresponding `discord.Emoji` object
            # - If the `react_emoji` is an integer object, it means that it is a Discord emoji, otherwise it is a unicode emoji
            react_emojis = [
                await interaction.guild.fetch_emoji(react_emoji) if isinstance(react_emoji, int) else react_emoji
                for react_emoji in channel_event["react_emojis"]
            ]
            await interaction.response.send_message(
                embed=ChannelEventDetailsEmbed(
                    interaction=interaction, react_emojis=react_emojis, ordered=channel_event["ordered"]
                )
            )

            embedded_message = await interaction.original_response()  # Obtain the embedded message

            # Apply the EditChannelEventDetailsView to the embedded message
            edit_channel_event_view = EditChannelEventDetailsView(
                channel_event=channel_event,
                embedded_message=embedded_message,
                react_emojis=react_emojis,
                interaction_user=interaction.user,
                timeout=180,
            )
            await interaction.edit_original_response(view=edit_channel_event_view)

            timeout = await edit_channel_event_view.wait()
            if timeout or edit_channel_event_view.is_cancelled:  # On timeout or view cancel
                await asyncio.gather(
                    interaction.delete_original_response(),
                    interaction.followup.send(
                        content="This command has timed out, please try again."
                        if timeout
                        else "Command cancelled. The channel event was not updated.",
                        ephemeral=True,
                    ),
                )
            else:
                te_conf.upsert_channel_event(
                    event=event.value,
                    channel_id=channel.id,
                    ordered=edit_channel_event_view.channel_event["ordered"],
                    react_emojis=edit_channel_event_view.enabled_react_emojis,
                    replace_reactions=True,
                )  # Update the channel event based on the interactions with the EditChannelEventDetailsView

                await asyncio.gather(
                    interaction.edit_original_response(view=None),
                    interaction.followup.send(content="Successfully updated channel event reactions", ephemeral=True),
                )  # Update embedded message
        else:  # No channel event found
            await interaction.response.send_message(content="No channel event found.", ephemeral=True)

    # =================================================================================================================
    # EVENT LISTENERS
    # =================================================================================================================
    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread):
        self.add_reactions_to_thread(thread=thread, event_type="on_thread_create")

    @commands.Cog.listener()
    async def on_thread_update(self, thread: discord.Thread):
        self.add_reactions_to_thread(thread=thread, event_type="on_thread_update")


async def setup(bot):
    await bot.add_cog(ThreadEvents(bot))
