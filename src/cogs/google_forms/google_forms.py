import asyncio
from typing import Literal, Optional

import discord
from discord import Permissions, app_commands
from discord.ext import commands

from src.cogs.google_forms.ui.views import AuthenticationLinkView
from src.modules.auth.google_credentials import GoogleCredentials
from src.modules.google_forms.service import GoogleFormsService
from src.modules.ui.custom import CancelView, ConfirmationView
from src.utils.config import GoogleCloudConfig
from src.utils.helper import send_or_edit_interaction_message
from src.utils.user_input import get_user_input


class GoogleForms(commands.GroupCog, name="google"):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.setup_callbacks = {"upsert": self.upsert, "delete": self.delete}
        self.setup_settings_callbacks = {
            "upsert": self.manage_default_channel,
            "delete": self.manage_default_channel,
            "login": self.manage_credentials,
            "logout": self.manage_credentials,
            "reset": self.reset_settings,
        }
        self.manage_form_feed_callbacks = {
            "create": self.create_feed,
            "update": self.edit_feed,
            "delete": self.delete_feed,
        }

    # =================================================================================================================
    # COMMAND GROUPS
    # =================================================================================================================
    forms_group = app_commands.Group(
        name="forms",
        description="Complete operations on Google Form links.",
        default_permissions=Permissions(manage_messages=True),
        guild_only=True,
    )

    async def get_form_id_from_link(self, interaction: discord.Interaction, link: str):
        try:
            return link.split("/")[-2]
        except IndexError:
            await interaction.response.send_message("Please ensure a valid form link is entered.", ephemeral=True)
            return None

    async def create_feed(
        self,
        interaction: discord.Interaction,
        form_id: str,
        event: Literal["RESPONSES", "SCHEMA"],
        channel: Optional[discord.TextChannel],
    ):
        gc_conf = GoogleCloudConfig()

        if not gc_conf.form_channel_id and not channel:
            return await interaction.response.send_message(content="", ephemeral=True)

        form_feed = gc_conf.search_active_form_watch(form_id=form_id, event_type=event)

        if form_feed:
            return await interaction.response.send_message(content="", ephemeral=True)

        try:
            await asyncio.gather(
                interaction.response.defer(ephemeral=True),
                GoogleCredentials.get_oauth_cred(on_discord=True, bot=self.bot, interaction=interaction),
            )
        except:
            return await send_or_edit_interaction_message(interaction=interaction, content="", ephemeral=True)

        form_service = GoogleFormsService.init_oauth()
        form_watch = await form_service.create_watch_list(interaction=interaction, form_id=form_id, event_type=event)
        content = "Failed to create form feed and retrieve form schema."

        if form_watch:
            channel_id = channel.id if channel else gc_conf.form_channel_id

            gc_conf.insert_new_form_watch(result=form_watch, form_id=form_id, channel_id=channel_id)

            content = f"Successfully created form feed in <#{channel_id}>"

            form_details = form_service.get_form_details(form_id=form_id)
            if form_details:
                gc_conf = GoogleCloudConfig()
                form_schema = gc_conf.get_schema_from_response(response=form_details)
                gc_conf.upsert_form_schema(form_id=form_id, schema=form_schema)
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
        gc_conf = GoogleCloudConfig()

        form_feed = gc_conf.search_active_form_watch(form_id=form_id, event_type=event)

        if not form_feed:
            return await interaction.response.send_message(content="", ephemeral=True)

        if not channel:
            return await interaction.response.send_message(content="", ephemeral=True)

        gc_conf.update_form_watch(form_id=form_id, event_type=event, channel_id=channel.id)
        await interaction.response.send_message(content="Successfully updated form watch.", ephemeral=True)

    async def delete_feed(
        self, interaction: discord.Interaction, form_id: str, event: Literal["RESPONSES", "SCHEMA"], *_
    ):
        gc_conf = GoogleCloudConfig()
        gc_conf.delete_form_watch(form_id=form_id, event_type=event)
        gc_conf.delete_form_schema(form_id=form_id)
        await interaction.response.send_message(content="", ephemeral=True)

    async def manage_default_channel(
        self,
        interaction: discord.Interaction,
        action: Literal["upsert", "delete"],
        channel: Optional[discord.TextChannel],
    ):
        gc_conf = GoogleCloudConfig()
        if action.value == "upsert":
            if not channel:
                return await interaction.response.send_message(
                    "To insert or update a form channel, please enter a Discord channel.", ephemeral=True
                )
            elif gc_conf.form_channel_id == channel.id:
                return await interaction.response.send_message(
                    content="Channel is already set as the form channel ID.", ephemeral=True
                )

        gc_conf.manage_channel(action=action, channel=channel)
        await interaction.response.send_message(
            content=f"The default channel has been successfully {'inserted or updated' if action == 'upsert' else 'deleted'}.",
            ephemeral=True,
        )

    async def manage_credentials(self, *, interaction: discord.Interaction, action: Literal["login", "logout"]):
        if action == "login":
            try:
                await GoogleCredentials.google_oauth_process(interaction=interaction, bot=self.bot)

                if not GoogleCredentials.OAUTH2_CLIENT_ID_CRED:
                    raise Exception("Authentication via Discord has failed.")

                await send_or_edit_interaction_message(
                    interaction=interaction, content="Successfully authenticated Google account.", ephemeral=True
                )
            except:
                return await interaction.followup.send(content="Failed to authenticate Google account.", ephemeral=True)
        else:
            GoogleCredentials.delete_credential_from_file("oauth2_client_id")
            await send_or_edit_interaction_message(
                interaction=interaction, content="Successfully logged out of Google feature.", ephemeral=True
            )

    async def reset_settings(self, *, interaction: discord.Interaction):
        GoogleCloudConfig().manage_channel(action="delete", channel=None)
        GoogleCredentials.delete_credential_from_file("oauth2_client_id")
        GoogleCredentials.delete_credential_from_file("service_account")
        await send_or_edit_interaction_message(
            interaction=interaction, content="Successfully reset default settings.", ephemeral=True
        )

    @app_commands.command(
        name="manage-settings", description="Setup default settings for the Google Workspace feature."
    )
    @app_commands.guild_only()
    @app_commands.describe(action="the action to execute", channel="the default channel where messages will be sent to")
    @app_commands.choices(
        action=[
            app_commands.Choice(name="CHANNEL: set or update the default channel (channel required)", value="upsert"),
            app_commands.Choice(name="CHANNEL: remove the default channel", value="delete"),
            app_commands.Choice(name="GOOGLE: login to Gmail account", value="login"),
            app_commands.Choice(name="GOOGLE: logout of Gmail account", value="logout"),
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
        await self.setup_settings_callbacks[action.value](interaction=interaction, action=action.value, channel=channel)

    @app_commands.command(
        name="manage-default-topic",
        description="Manage the default Google Pub/Sub topic that publishes messages to Discord channels.",
    )
    @app_commands.guild_only()
    @app_commands.rename(topic_name="topic")
    @app_commands.describe(
        action="the action to execute", topic_name="the Google Pub/Sub topic to subscribe/unsubscribe to"
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="enter a new subscription", value="subscribe"),
            app_commands.Choice(name="replace the default subscription", value="unsubscribe"),
        ]
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def manage_default_topic(
        self, interaction: discord.Interaction, action: app_commands.Choice[str], topic_name: Optional[str]
    ):
        gc_conf = GoogleCloudConfig()
        if action.value == "subscribe":
            if not topic_name:
                return await interaction.response.send_message(content="", ephemeral=True)

            if gc_conf.default_topic:
                confirmation_view = ConfirmationView(timeout=180)

                topic_embed = discord.Embed(
                    title="Default Topic Subscription Exists",
                    description=f'A topic with the name "{gc_conf.default_topic}" is already subscribed to. Would you like to replace this topic subscription?',
                )

                await asyncio.gather(
                    interaction.response.send_message(embed=topic_embed, view=confirmation_view, ephemeral=True),
                    confirmation_view.wait(),
                )

                if not confirmation_view.is_confirmed:
                    return await send_or_edit_interaction_message(
                        interaction=interaction, edit_original_response=True, content="", ephemeral=True
                    )

            gc_conf.set_default_topic(topic_name=topic_name)
            await send_or_edit_interaction_message(
                interaction=interaction, edit_original_response=True, content="", ephemeral=True
            )
        else:
            gc_conf.set_default_topic(None)
            await send_or_edit_interaction_message(interaction=interaction, content="", ephemeral=True)

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
        form_id = self.get_form_id_from_link(interaction=interaction, link=link)

        if form_id:
            await self.manage_form_feed_callbacks[action.value](
                interaction=interaction, form_id=form_id, event=event.value, channel=channel
            )

    @forms_group.command(name="refresh-schema")
    @app_commands.guild_only()
    @app_commands.describe(link="**edit link** for the Google Forms")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def refresh_form_schema(self, interaction: discord.Interaction, link: str):
        form_id = self.get_form_id_from_link(interaction=interaction, link=link)

        if form_id:
            form_service = GoogleFormsService.init_service_acc()
            form_details = form_service.get_form_details(form_id=form_id)

            if form_details:
                gc_conf = GoogleCloudConfig()
                form_schema = gc_conf.get_schema_from_response(response=form_details)
                gc_conf.upsert_form_schema(form_id=form_id, schema=form_schema)
                await interaction.response.send_message(content="", ephemeral=True)
            else:
                await interaction.response.send_message(content="", ephemeral=True)


async def setup(bot):
    await bot.add_cog(GoogleForms(bot))
