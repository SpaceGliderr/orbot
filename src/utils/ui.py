import traceback
from typing import Any, List, Optional, Union

import discord


class Select(discord.ui.Select):
    def __init__(
        self,
        *,
        placeholder: Optional[str] = None,
        min_values: int = 1,
        max_values: int = 1,
        options: List[discord.SelectOption],
        disabled: bool = False,
        custom_id: Optional[str] = None,
        row: Optional[int] = None,
        stop_view: bool = False,
        defer: bool = False,
    ) -> None:
        super().__init__(
            placeholder=placeholder,
            min_values=min_values,
            max_values=max_values,
            options=options,
            disabled=disabled,
            row=row,
            custom_id=custom_id,
        )
        self.stop_view = stop_view
        self.defer = defer

    async def callback(self, interaction: discord.Interaction):
        if self.stop_view:
            self.view.stop()

        if self.defer:
            await interaction.response.defer()

        self.view.values = self.values
        self.view.interaction = interaction


class Button(discord.ui.Button):
    def __init__(
        self,
        *,
        style: discord.ButtonStyle = discord.ButtonStyle.primary,
        label: Optional[str] = None,
        disabled: bool = False,
        custom_id: Optional[str] = None,
        url: Optional[str] = None,
        emoji: Optional[Union[str, discord.Emoji, discord.PartialEmoji]] = None,
        row: Optional[int] = None,
        value: Optional[Any] = None,
        stop_view: bool = False,
        defer: bool = False,
    ):
        super().__init__(
            label=label, disabled=disabled, custom_id=custom_id, url=url, emoji=emoji, row=row, style=style
        )
        self.value = value
        self.stop_view = stop_view
        self.defer = defer

    async def callback(self, interaction: discord.Interaction):
        if self.stop_view:
            self.view.stop()

        if self.defer:
            await interaction.response.defer()

        if self.value is not None:
            self.view.values = self.value
        else:
            self.view.values = self.label

        self.view.interaction = interaction


class View(discord.ui.View):
    def __init__(self, *, timeout: Optional[float] = None):
        super().__init__(timeout=timeout)
        self.values = None
        self.interaction: Optional[discord.Interaction] = None


class Modal(discord.ui.Modal):
    def __init__(self, *, title: str, timeout: Optional[float] = None, custom_id: Optional[str] = None) -> None:
        super().__init__(title=title, timeout=timeout, custom_id=custom_id)

    def get_values(self):
        return {child.custom_id: child.value for child in self.children if child.value}

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"Thanks for your feedback!", ephemeral=True)

        self.stop()

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        await interaction.response.send_message("Oops! Something went wrong.", ephemeral=True)

        traceback.print_tb(error.__traceback__)
