from math import floor
from typing import List, Optional

import discord
from dateutil import parser

from src.modules.ui.common import Modal, View
from src.utils.helper import get_from_dict


class FormWatchDetailsEmbed(discord.Embed):
    """Creates an embed that displays the configuration information of a Google Form watch.

    Parameters
    ----------
        * form_watch: :class:`dict`
            - The form watch object saved in the `google_cloud.yaml` file.
        * form_schema: Optional[:class:`dict`]
            - The form schema. If no form schema is provided, it will just show the form ID.
    """

    def __init__(self, form_watch: dict, form_schema: Optional[dict], *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.title = "Form Watch Details"
        self.description = (
            f"Form watch details for the `{form_schema['info']['title']}` form with the form ID of `{form_watch['form_id']}`"
            if form_schema
            else f"Form watch details for form with a form ID of `{form_watch['form_id']}`"
        )

        self.add_field(name="Watch ID", value=form_watch["watch_id"], inline=False)
        self.add_field(name="Google Topic Name", value=form_watch["topic_name"], inline=False)
        self.add_field(name="Broadcast Channel", value=f"<#{form_watch['broadcast_channel_id']}>")
        self.add_field(name="Watch Event Type", value=form_watch["event_type"])
        self.add_field(
            name="Expiry Date & Time", value=f"<t:{floor(parser.parse(form_watch['expire_time']).timestamp())}:F>"
        )


class FormSchemaInfoEmbed(discord.Embed):
    """Creates an embed that displays the form schema details of a Google Form.

    Parameters
    ----------
        * form_schema: :class:`dict`
        * form_id: :class:`str`
    """

    def __init__(self, form_schema: dict, form_id: str, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.title = "Form Information"
        self.description = (
            f"Form watch details for the `{form_schema['info']['title']}` form with the form ID of `{form_id}`"
        )

        linked_sheet_id = get_from_dict(form_schema, ["linked_sheet_id"])

        self.add_field(name="Form Title", value=form_schema["info"]["title"], inline=False)
        self.add_field(name="Form Description", value=form_schema["info"]["description"], inline=False)
        self.add_field(
            name="Linked Sheet ID",
            value=linked_sheet_id if linked_sheet_id else "_<No Google Sheet was linked to this form>_",
            inline=False,
        )


class FormSchemaQuestionsEmbed(discord.Embed):
    """Creates an embed that displays the form schema questions of a Google Form.

    Parameters
    ----------
        * form_title: :class:`str`
        * form_id: :class:`str`
        * questions: List[:class: dict]
            - The questions to display in the embed fields.
    """

    def __init__(self, form_title: str, form_id: str, questions: List[dict], *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.title = "Form Questions"
        self.description = (
            f"Viewing the cached form questions for the `{form_title}` form with the form ID of `{form_id}`"
        )

        for idx, question in enumerate(questions):
            self.add_field(name=f"Question {idx+1}", value=question["title"])


class GoogleTopicStatusEmbed(discord.Embed):
    """Creates an embed that displays the thread statuses of the Google Topic Listeners.

    Parameters
    ----------
        * topic_listeners: List[:class: tuple]
    """

    def __init__(self, topic_listeners: List[tuple], *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.title = "Google Topic Status"

        for topic_listener in topic_listeners:
            self.add_field(
                name=f"Status for {topic_listener[0]}",
                value="🟢 Alive" if topic_listener[1].is_alive() else "🔴 Dead",
                inline=False,
            )


class AuthenticationCodeModal(Modal):
    """Creates a modal popup window to obtain an authentication code by inheriting the `Modal` class. Has 1 text inputs for `auth_code`."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.add_item(
            discord.ui.TextInput(
                label="Authentication Code",
                placeholder="Enter authentication code",
                custom_id="auth_code",
                required=True,
            )
        )


class AuthenticationLinkView(View):
    """Creates a view to redirect users to an authentication link and obtain the authentication code using the `AuthenticationCodeModal` by inheriting the `View` class.

    Parameters
    ----------
        * auth_url: :class:`str`
            - The authentication link to redirect users to authenticate their Google account.
    """

    def __init__(self, auth_url: str, timeout: Optional[float] = None):
        super().__init__(timeout=timeout)

        self.interaction = None
        self.auth_code = None
        self.is_cancelled = False

        self.add_item(
            discord.ui.Button(style=discord.ButtonStyle.link, url=auth_url, label="Authenticate with Google", row=0)
        )  # Redirect button to redirect the user to the auth url

    @discord.ui.button(label="Enter Authentication Code", style=discord.ButtonStyle.primary, row=1)
    async def enter_code(self, interaction: discord.Interaction, *_):
        """A button callback that sends a `AuthenticationCodeModal` modal and obtains the authentication code from the user."""
        auth_code_modal = AuthenticationCodeModal(title="Enter Authentication Code", timeout=20)
        await interaction.response.send_modal(auth_code_modal)

        timeout = await auth_code_modal.wait()
        if not timeout:
            self.auth_code = auth_code_modal.get_values()["auth_code"]
            self.interaction = interaction
            self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, emoji="✖️", row=1)
    async def cancel(self, interaction: discord.Interaction, *_):
        await interaction.response.defer()
        self.is_cancelled = True
        self.interaction = interaction
        self.stop()
