import traceback
from typing import Any, List, Optional, Union

import discord


class Select(discord.ui.Select):
    """An extension of the `discord.ui.Select` UI class provided by `discord.py`.

    This class has all the constructor and attributes of the `discord.ui.Select` class.

    Additional Parameters and Attributes
    ----------
        * stop_view: :class:`bool`
            - Stops the parent view if `True`.
        * defer: :class:`bool`
            - Defers the Interaction in the Buttons callback.
    """

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
    """An extension of the `discord.ui.Button` UI class provided by `discord.py`.

    This class has all the constructor and attributes of the `discord.ui.Button` class.

    Additional Parameters and Attributes
    ----------
        * value: Optional[:class:`Any`]
            - Stores the value of a Button item. If no value is provided, the label is taken as the value.
        * stop_view: :class:`bool`
            - Stops the parent view if `True`.
        * defer: :class:`bool`
            - Defers the Interaction in the Buttons callback.
    """

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
    """An extension of the `discord.ui.View` UI class provided by `discord.py`.

    This class has all the constructor and attributes of the `discord.ui.View` class.

    Additional Attributes
    ----------
        * values: Optional[:class:`Any`]
            - Stores the values from an item. Can only store results from one item. Can be `None` type.
        * interaction: Optional[:class:`discord.Interaction`]
            - Returns the Interaction object from an item. Can only return one Interaction object from one item. Can be `None` type.
    """

    def __init__(self, *, timeout: Optional[float] = None):
        super().__init__(timeout=timeout)
        self.values = None
        self.interaction: Optional[discord.Interaction] = None


class Modal(discord.ui.Modal):
    """An extension of the `discord.ui.Modal` UI class provided by `discord.py`.

    This class has all the constructor and attributes of the `discord.ui.Modal` class.

    Additional Parameters and Attributes
    ----------
        * success_msg: Optional[:class:`str`]
            - Displays a success response. If `None` is provided, the Interaction is deferred.
        * error_msg: Optional[:class:`str`]
            - Displays an error response. If `None` is provided, the Interaction is deferred.
    """

    def __init__(
        self,
        *,
        title: str,
        timeout: Optional[float] = None,
        custom_id: Optional[str] = None,
        success_msg: Optional[str] = None,
        error_msg: Optional[str] = None,
    ) -> None:
        super().__init__(title=title, timeout=timeout, custom_id=custom_id)
        self.success_msg = success_msg
        self.error_msg = error_msg

    def get_values(self):
        return {child.custom_id: child.value for child in self.children if child.value}

    async def on_submit(self, interaction: discord.Interaction):
        if self.success_msg is not None:
            await interaction.response.send_message(f"{self.success_msg}", ephemeral=True)
        else:
            await interaction.response.defer()

        self.stop()

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        if self.error_msg is not None:
            await interaction.response.send_message(f"{self.error_msg}", ephemeral=True)
        else:
            await interaction.response.defer()

        traceback.print_tb(error.__traceback__)
