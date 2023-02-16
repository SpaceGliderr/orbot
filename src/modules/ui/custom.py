from typing import List, Optional

import discord

from src.modules.ui.common import View


class CancelView(View):
    """Creates a view with a cancel button by inheriting the `View` class."""

    def __init__(self, *, timeout: Optional[float] = None):
        super().__init__(timeout=timeout)
        self.interaction = None

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, emoji="✖️")
    async def cancel(self, interaction: discord.Interaction, *_):
        await interaction.response.defer()
        self.interaction = interaction
        self.stop()


class PaginatedEmbedsView(View):
    """Creates a paginated embed view. Has previous, next and lock buttons.

    Additional Parameters
    ----------
        * embeds: :class:`list`
            - List of embeds to iterate through.
    """

    def __init__(self, embeds: List[discord.Embed], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.embeds = embeds
        self.curr_idx = 0

    def update_curr_idx(self, increment: int):
        """Updates the current index of the list of embeds"""
        if self.curr_idx + increment == len(self.embeds):
            self.curr_idx = 0
        elif self.curr_idx + increment < 0:
            self.curr_idx = len(self.embeds) - 1
        else:
            self.curr_idx = self.curr_idx + increment

        return self.curr_idx

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.primary, emoji="⬅️")
    async def previous(self, interaction: discord.Interaction, *_):
        self.value = False
        await interaction.response.edit_message(embed=self.embeds[self.update_curr_idx(-1)])

    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary, emoji="➡️")
    async def next(self, interaction: discord.Interaction, *_):
        self.value = True
        await interaction.response.edit_message(embed=self.embeds[self.update_curr_idx(1)])

    @discord.ui.button(style=discord.ButtonStyle.red, emoji="🔒")
    async def lock(self, interaction: discord.Interaction, *_):
        self.stop()
        await interaction.response.edit_message(view=None)


class ConfirmationView(View):
    """Creates a view with a yes and no button by inheriting the `View` class."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_confirmed = False

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.green, emoji="⬅️")
    async def yes(self, interaction: discord.Interaction, *_):
        await interaction.response.defer()
        self.is_confirmed = True
        self.stop()

    @discord.ui.button(label="No", style=discord.ButtonStyle.red, emoji="➡️")
    async def no(self, interaction: discord.Interaction, *_):
        await interaction.response.defer()
        self.stop()
