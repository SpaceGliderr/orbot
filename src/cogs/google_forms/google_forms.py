import asyncio
import datetime
import logging
import os
from typing import Literal, Optional

import discord
from dateutil import parser
from discord import Permissions, app_commands
from discord.ext import commands, tasks
from google.oauth2 import credentials as oauth2_credentials

from src.modules.auth.google_credentials import GoogleCredentialsHelper
from src.modules.google_forms.forms import GoogleFormsHelper
from src.modules.google_forms.service import GoogleFormsService
from src.modules.ui.custom import ConfirmationView, PaginatedEmbedsView
from src.utils.config import GoogleCloudConfig
from src.utils.helper import send_or_edit_interaction_message


class GoogleForms(commands.GroupCog, name="google"):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.setup_settings_callbacks = {
            "upsert": self.manage_default_channel,
            "delete": self.manage_default_channel,
            "reset": self.reset_settings,
        }
        self.manage_form_feed_callbacks = {
            "create": self.create_feed,
            "update": self.edit_feed,
            "delete": self.delete_feed,
        }

        self.renew_watches_task.start()

    # =================================================================================================================
    # COMMAND GROUPS
    # =================================================================================================================
    forms_group = app_commands.Group(
        name="forms",
        description="Complete operations on Google Form links.",
        default_permissions=Permissions(manage_messages=True),
        guild_only=True,
    )

    def cog_unload(self) -> None:
        self.renew_watches_task.cancel()

    # =================================================================================================================
    # GENERAL FUNCTIONS
    # =================================================================================================================
    async def get_form_id_from_link(self, interaction: discord.Interaction, link: str):
        """A method to get the form ID from an editable Google form link.

        Parameters
        ----------
            * interaction: :class:`discord.Interaction`
                - The interaction instance to send a response message.
            * link: :class:`str`
                - The link to extract the form ID from.

        Returns
        ----------
            * `str` | `None`
        """
        try:  # Enclosed in a try-except block to handle the case where it is an empty list / a list which does not have enough elements
            return link.split("/")[-2]
        except IndexError:
            await interaction.response.send_message("Please ensure a valid form link is entered.", ephemeral=True)
            return None

    # =================================================================================================================
    # MANAGE DEFAULT SETTING FUNCTIONS
    # =================================================================================================================
    async def manage_default_channel(
        self,
        interaction: discord.Interaction,
        action: Literal["upsert", "delete"],
        channel: Optional[discord.TextChannel],
    ):
        """Allows the user to insert, update, and delete the default broadcast channel of the form feeds.

        Parameters
        ----------
            * interaction: :class:`discord.Interaction`
                - The interaction instance to send a response message.
            * action: :class:`Literal["upsert", "delete"]`
                - The action to perform on the default broadcast channel.
            * channel: Optional[:class:`discord.TextChannel`]
                - The channel to replace the default broadcast channel with. This argument must be provided to complete an `upsert` action.
        """
        gc_conf = GoogleCloudConfig()

        if action == "upsert":
            if not channel:  # Check whether channel is present during an `upsert` action
                return await interaction.response.send_message(
                    "To insert or update a form channel, please enter a Discord channel.", ephemeral=True
                )
            elif (
                gc_conf.form_channel_id == channel.id
            ):  # Check whether the current default broadcast channel is equal to the new broadcast channel
                return await interaction.response.send_message(
                    content="Channel is already set as the form channel ID.", ephemeral=True
                )

        # Update the `google_cloud.yaml` file
        gc_conf.manage_channel(action=action, channel=channel)
        await interaction.response.send_message(
            content=f"The default channel has been successfully {'inserted or updated' if action == 'upsert' else 'deleted'}.",
            ephemeral=True,
        )

    async def reset_settings(self, interaction: discord.Interaction, **_):
        """Resets all default settings of the entire Google module - default broadcast channels, cached OAuth and service account credentials.

        Parameters
        ----------
            * interaction: :class:`discord.Interaction`
                - The interaction instance to send a response message.
            * action: :class:`Literal["login", "logout"]`
                - The action to perform on the Google account.
        """
        GoogleCloudConfig().manage_channel(action="delete", channel=None)
        await send_or_edit_interaction_message(
            interaction=interaction, content="Successfully reset default settings.", ephemeral=True
        )

    # =================================================================================================================
    # MANAGE FEED FUNCTIONS
    # =================================================================================================================
    async def create_feed(
        self,
        interaction: discord.Interaction,
        form_id: str,
        event: Literal["RESPONSES", "SCHEMA"],
        channel: Optional[discord.TextChannel],
    ):
        """Handles creating a Google form watch, retrieving the form schema, and updating relevant information if it already exists.

        Parameters
        ----------
            * interaction: :class:`discord.Interaction`
                - The interaction instance to send a response message.
            * form_id: :class:`str`
                - The form ID to create the stream for.
            * event: :class:`Literal["RESPONSES", "SCHEMA"]`
                - The form event to watch for. The "RESPONSES"
            * channel: Optional[:class:`discord.TextChannel`]
                - Broadcast channel for the responses of the listened form event. If `None` is provided, it uses the default broadcast channel set in the `google_cloud.yaml` file. Otherwise, it will not create the form feed.
        """
        gc_conf = GoogleCloudConfig()

        if (
            not gc_conf.form_channel_id and not channel
        ):  # If the `channel` variable is not provided and there is no default broadcast channel setup, don't proceed
            return await interaction.response.send_message(
                content="Please enter a broadcast channel or set the default channel using the `setup` command to create a feed.",
                ephemeral=True,
            )

        form_feed = gc_conf.search_active_form_watch(
            form_id=form_id, event_type=event
        )  # Search for currently active form feeds

        if form_feed:  # If the feed already exists, redirect the user to use the `update` command instead
            current_date = datetime.date.today()
            expiry_date = parser.parse(form_feed["expire_time"]).date()

            delta_days = (expiry_date - current_date).days

            if delta_days < 0:
                gc_conf.delete_form_watch(
                    form_id=form_id,
                    watch_id=form_feed["watch_id"],
                    event_type=form_feed["event_type"],
                    topic_name=form_feed["topic_name"],
                )
            else:
                return await interaction.response.send_message(
                    content="A feed for the form and specific form event already exists. Please use the `update form` command to update the feed details.",
                    ephemeral=True,
                )

        oauth_cred = await GoogleCredentialsHelper.google_oauth_discord_flow(interaction=interaction)

        if isinstance(oauth_cred, oauth2_credentials.Credentials):
            # Instantiate OAuth version of the GoogleFormsService class
            # Needs to be OAuth credentials because the current Google Form API for creating form watches does not support service account credentials
            # Link to issue: https://issuetracker.google.com/issues/242295786
            # TODO: Consolidate all credentials to service account credentials instead of OAuth credentials
            form_service = GoogleFormsService(credentials=oauth_cred)

            # Create form watch using the form service
            form_watch = form_service.create_form_watch(
                form_id=form_id, event_type=event, topic_name=os.getenv("DEFAULT_FORMS_TOPIC_NAME")
            )

            content = "Failed to create form feed and retrieve form schema."  # Keep track of the return message

            if form_watch:
                # Insert the created form watch into the `google_cloud.yaml` file
                channel_id = channel.id if channel else gc_conf.form_channel_id
                gc_conf.insert_new_form_watch(result=form_watch, form_id=form_id, channel_id=channel_id)
                content = f"Successfully created form feed in <#{channel_id}>"

                # Get the form details
                form_details = form_service.get_form_details(form_id=form_id)
                if form_details:
                    # Generate the schema from the form details
                    form_schema = GoogleFormsHelper.generate_schema(response=form_details)

                    # Insert a new/update an existing schema into the `google_cloud.yaml` file
                    GoogleCloudConfig().upsert_form_schema(form_id=form_id, schema=form_schema)

                    content += f" and retrieved form schema for form with ID of {form_id}."
                else:
                    content += f", but failed to retrieve form schema for form with ID of {form_id}."

            await send_or_edit_interaction_message(interaction=interaction, content=content, ephemeral=True)

    async def edit_feed(
        self,
        interaction: discord.Interaction,
        form_id: str,
        event: Literal["RESPONSES", "SCHEMA"],
        channel: Optional[discord.TextChannel],
    ):
        """Handles creating a Google form watch, retrieving the form schema, and updating relevant information if it already exists.

        Parameters
        ----------
            * interaction: :class:`discord.Interaction`
                - The interaction instance to send a response message.
            * form_id: :class:`str`
                - The form ID to edit the stream for.
            * event: :class:`Literal["RESPONSES", "SCHEMA"]`
                - A filter to select the specific form feed to edit.
            * channel: Optional[:class:`discord.TextChannel`]
                - Broadcast channel for the responses of the listened form event. If `None` is provided, it uses the default broadcast channel set in the `google_cloud.yaml` file. Otherwise, it will not create the form feed.
        """
        gc_conf = GoogleCloudConfig()

        form_feed = gc_conf.search_active_form_watch(
            form_id=form_id, event_type=event
        )  # Search for currently active form feeds

        if not form_feed:
            return await interaction.response.send_message(
                content="A feed for the form and specific form event does not exist. Please use the `create form` command to create a new feed.",
                ephemeral=True,
            )

        if (
            not channel and not gc_conf.default_topic
        ):  # Ensure that a default channel exists if there is no `channel` provided
            return await interaction.response.send_message(
                content="To update feed please provide a Discord channel or set the default channel using the `setup` command.",
                ephemeral=True,
            )

        if not channel:
            # If no channel is provided, it will replace the current broadcast channel with the default channel
            # Before replacing the broadcast channel with the default channel, send a confirmation view to confirm whether the user wants to replace it with the default one or not
            confirmation_embed = discord.Embed(
                title="Resetting Broadcast Channel",
                description="You did not specify a Discord channel when updating the feed. This will replace the current broadcast channel to the default channel.",
            )
            confirmation_view = ConfirmationView(timeout=180)
            await asyncio.gather(
                interaction.response.send_message(embed=confirmation_embed, view=confirmation_view, ephemeral=True),
                confirmation_view.wait(),
            )

            if not confirmation_view.is_confirmed:
                return await send_or_edit_interaction_message(
                    interaction=interaction,
                    edit_original_response=True,
                    content="The feed was not updated.",
                    view=None,
                    embed=None,
                    ephemeral=True,
                )

        # Update the form watch in the `google_cloud.yaml` file
        gc_conf.update_form_watch(
            form_id=form_id, event_type=event, channel_id=channel.id if channel else gc_conf.default_topic
        )

        await send_or_edit_interaction_message(
            interaction=interaction,
            edit_original_response=True,
            content="Successfully updated form watch.",
            view=None,
            embed=None,
            ephemeral=True,
        )

    async def delete_feed(
        self, interaction: discord.Interaction, form_id: str, event: Literal["RESPONSES", "SCHEMA"], *_
    ):
        """Deletes a form feed and form schema from the `google_cloud.yaml` file. This does not delete the form watch itself.

        Parameters
        ----------
            * interaction: :class:`discord.Interaction`
                - The interaction instance to send a response message.
            * form_id: :class:`str`
                - The form ID to create the stream for.
            * event: :class:`Literal["RESPONSES", "SCHEMA"]`
        """
        try:
            gc_conf = GoogleCloudConfig()
            gc_conf.delete_form_watch(form_id=form_id, event_type=event)
            gc_conf.delete_form_schema(form_id=form_id)
            await interaction.response.send_message(
                content="Successfully deleted form feed and form schema.", ephemeral=True
            )
        except:
            await interaction.response.send_message(
                content="Failed to delete form feed and form schema.", ephemeral=True
            )

    # =================================================================================================================
    # GENERAL SLASH COMMANDS
    # =================================================================================================================
    @app_commands.command(
        name="manage-default-settings", description="Setup default settings for the Google Workspace feature."
    )
    @app_commands.guild_only()
    @app_commands.describe(action="the action to execute", channel="the default channel where messages will be sent to")
    @app_commands.choices(
        action=[
            app_commands.Choice(name="CHANNEL: set or update the default channel (channel required)", value="upsert"),
            app_commands.Choice(name="CHANNEL: remove the default channel", value="delete"),
            app_commands.Choice(name="reset default settings", value="reset"),
        ]
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def manage_settings(
        self,
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        channel: Optional[discord.TextChannel] = None,
    ):
        """A slash command that allows the user to manage the default settings of the Google module."""
        await self.setup_settings_callbacks[action.value](interaction=interaction, action=action.value, channel=channel)

    @app_commands.command(
        name="manage-topics", description="Manage the Google Pub/Sub topic that publishes messages to Discord channels."
    )
    @app_commands.guild_only()
    @app_commands.rename(topic_name="topic")
    @app_commands.describe(
        action="the action to execute", topic_name="the Google Pub/Sub topic to subscribe/unsubscribe to"
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="enter a new subscription (topic name required)", value="subscribe"),
            app_commands.Choice(name="replace the default subscription", value="unsubscribe"),
        ]
    )
    @app_commands.checks.has_permissions()
    async def manage_topics(self, interaction: discord.Interaction, action: app_commands.Choice[str], topic_name: str):
        """A slash command that allows the user to manage the list of subscribed topics of the Google module.

        Parameters
        ----------
            * interaction: :class:`discord.Interaction`
            * action: app_commands.Choice[:class:`str`]
                - The action to perform on the provided topic.
            * topic_name: Optional[:class:`str`]
                - The topic name to carry out the action on. To subscribe, a `topic_name` must be provided.
        """
        gc_conf = GoogleCloudConfig()

        if action.value == "subscribe":
            if gc_conf.subscribe_topic(topic_name=topic_name):
                self.bot.listener.start_stream(
                    topic_subscription_path=topic_name, client=self.bot, client_loop=self.bot.loop
                )
                await send_or_edit_interaction_message(
                    interaction=interaction, content="Successfully subscribed to topic", ephemeral=True
                )
            else:
                await send_or_edit_interaction_message(
                    interaction=interaction, content="Topic is already subscribed to", ephemeral=True
                )

        else:
            if gc_conf.unsubscribe_topic(topic_name=topic_name):
                self.bot.listener.close_stream(topic_subscription_path=topic_name)
                await send_or_edit_interaction_message(
                    interaction=interaction, content="Successfully unsubscribed from topic", ephemeral=True
                )
            else:
                await send_or_edit_interaction_message(
                    interaction=interaction, content="Topic is not subscribed to", ephemeral=True
                )

    @forms_group.command(name="manage-feed")
    @app_commands.guild_only()
    @app_commands.rename(link="form_link", event="listen_to", channel="broadcast_channel")
    @app_commands.describe(
        action="the action to perform on the provided Google Form",
        link="**edit link** for the Google Forms",
        event="form events to be broadcasted to the broadcast channel",
        channel="the broadcast location (if no channels are given, the default channel set using `setup` is used)",
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="create a new form feed", value="create"),
            app_commands.Choice(name="update an existing form feed", value="update"),
            app_commands.Choice(name="delete an existing form feed", value="delete"),
        ],
        event=[
            app_commands.Choice(name="new responses being submitted", value="RESPONSES"),
            app_commands.Choice(name="form schema changes", value="SCHEMA"),
        ],
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def manage_form_feed(
        self,
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        link: str,
        event: app_commands.Choice[str],
        channel: Optional[discord.TextChannel] = None,
    ):
        """A slash command that allows the user to manage the form feeds."""
        form_id = await self.get_form_id_from_link(interaction=interaction, link=link)

        if form_id:
            await self.manage_form_feed_callbacks[action.value](
                interaction=interaction, form_id=form_id, event=event.value, channel=channel
            )

    @forms_group.command(name="refresh-schema")
    @app_commands.guild_only()
    @app_commands.describe(link="**edit link** for the Google Forms")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def refresh_form_schema(self, interaction: discord.Interaction, link: str):
        """A slash command that allows the user to refresh the form schema of an editable Google Form link.

        Parameters
        ----------
            * interaction: :class:`discord.Interaction`
            * link: :class:`str`
                - The editable Google Form link.
        """
        form_id = await self.get_form_id_from_link(interaction=interaction, link=link)

        if (
            form_id
        ):  # If there is no `form_id`, the `get_form_id_from_link` already responds to the interaction, therefore there is no need to handle that scenario here
            form_service = (
                GoogleFormsService.init_service_acc()
            )  # Instantiate a GoogleFormService class using the service account credentials
            form_details = form_service.get_form_details(form_id=form_id)  # Get the form details

            if form_details:
                gc_conf = GoogleCloudConfig()
                form_schema = GoogleFormsHelper.generate_schema(
                    response=form_details
                )  # Generate the schema from the form details
                gc_conf.upsert_form_schema(
                    form_id=form_id, schema=form_schema
                )  # Upsert the schema into the `google_cloud.yaml` file

                await interaction.response.send_message(content="Successfully refreshed form schema.", ephemeral=True)
            else:
                await interaction.response.send_message(
                    content="Form schema refresh has failed. Could not find form details.", ephemeral=True
                )

    async def view_active_form_watches(self, interaction: discord.Interaction):
        pass

    # =================================================================================================================
    # ROUTINE TASK FUNCTIONS
    # =================================================================================================================
    # TODO: Add a task that updates every 24 hours, checks the google cloud yaml file for watches that are about to expire on that day, and then renew them
    # Refer to this documentation https://discordpy.readthedocs.io/en/latest/ext/tasks/
    @tasks.loop(time=datetime.time(hour=23, minute=0, tzinfo=datetime.timezone(offset=datetime.timedelta(hours=8))))
    async def renew_watches_task(self):
        form_service = GoogleFormsService.init_service_acc()

        gc_conf = GoogleCloudConfig()
        data = gc_conf.get_data()

        expired_watches_with_idx = []

        for watches in gc_conf.active_form_watches.values():
            for idx, watch in enumerate(watches):
                print("Watch >>> ", watch)

                current_date = datetime.date.today()
                expiry_date = parser.parse(watch["expire_time"]).date()

                delta_days = (expiry_date - current_date).days

                print("Delta Days >>> ", delta_days)

                if delta_days < 0:
                    expired_watches_with_idx.append([idx, watch])
                elif delta_days <= 1:
                    renewed_watch = form_service.renew_form_watch(form_id=watch["form_id"], watch_id=watch["watch_id"])
                    print("Watch Renewed >>> ", renewed_watch)

                    if renewed_watch:
                        data[watch["form_id"]][idx]["expire_time"] = renewed_watch["expire_time"]
                    else:
                        logging.info(f"Failed to renew watch with watch ID of {watch['watch_id']}")

        gc_conf.dump(data=data)

        if len(expired_watches_with_idx) > 0:
            gc_conf = GoogleCloudConfig()
            gc_conf.delete_form_watches_with_index(form_watches=expired_watches_with_idx)

            if gc_conf.form_channel_id:
                guild = await self.bot.fetch_guild(864118528134742026)
                channel = await guild.fetch_channel(gc_conf.form_channel_id)

                _, expired_watches = zip(*expired_watches_with_idx)
                expired_form_embeds = GoogleFormsHelper.generate_expired_form_watch_embeds(
                    expired_watches=expired_watches
                )

                await channel.send(
                    embed=expired_form_embeds[0],
                    view=None if len(expired_form_embeds) == 1 else PaginatedEmbedsView(embeds=expired_form_embeds),
                )


async def setup(bot):
    await bot.add_cog(GoogleForms(bot))
