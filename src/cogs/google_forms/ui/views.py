from typing import Optional

import discord

from src.modules.ui.common import Modal, View


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
