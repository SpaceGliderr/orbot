from typing import List, Optional

import discord

from src.modules.ui.common import Modal, View


class AuthenticationCodeModal(Modal):
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
    def __init__(self, auth_url: str, timeout: Optional[float] = None):
        super().__init__(timeout=timeout)
        self.interaction = None
        self.auth_code = None
        self.is_cancelled = False

        self.add_item(
            discord.ui.Button(style=discord.ButtonStyle.link, url=auth_url, label="Authenticate with Google", row=0)
        )

    @discord.ui.button(label="Enter Authentication Code", style=discord.ButtonStyle.primary, row=1)
    async def enter_code(self, interaction: discord.Interaction, *_):
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
