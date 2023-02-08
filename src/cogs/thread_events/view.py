import asyncio
from typing import Awaitable, List, Union

import discord

from src.modules.ui.common import Button, View
from src.utils.helper import send_or_edit_interaction_message

class ChannelEventDetailsEmbed(discord.Embed):
    def __init__(
        self, interaction: discord.Interaction, react_emojis: List[discord.Emoji | str], ordered: bool, *args, **kwargs
    ):
        super().__init__(*args, **kwargs)

        self.title = "Channel Event Details"
        self.set_author(name=interaction.user.display_name, icon_url=interaction.user.avatar)

        self.add_field(
            name="Reactions",
            value=", ".join([str(react_emoji) for react_emoji in react_emojis]),
            inline=False,
        )
        self.add_field(name="Ordered", value="Yes" if ordered else "No", inline=False)


class ReplaceReactEmojiViewEmbed(discord.Embed):
    def __init__(
        self,
        interaction: discord.Interaction,
        react_emojis: List[discord.Emoji | str],
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.title = "Channel Event Details"
        self.set_author(name=interaction.user.display_name, icon_url=interaction.user.avatar)

        self.add_field(
            name="Reactions",
            value=", ".join([str(react_emoji) for react_emoji in react_emojis]),
            inline=False,
        )


class ReplaceReactEmojiView(View):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.replace = False
        self.is_cancelled = False

    @discord.ui.button(label="Add to Existing", style=discord.ButtonStyle.green, emoji="➕")
    async def add(self, interaction: discord.Interaction, *_):
        await interaction.response.defer()
        self.stop()

    @discord.ui.button(label="Replace Existing", style=discord.ButtonStyle.grey, emoji="♻️")
    async def replace(self, interaction: discord.Interaction, *_):
        await interaction.response.defer()
        self.replace = True
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, *_):
        await interaction.response.defer()
        self.is_cancelled = True
        self.stop()


class NavigateReactEmojiView(View):
    def __init__(
        self,
        embedded_message: Union[discord.Message, discord.InteractionMessage],
        react_emoji_strs: List[str | int],
        react_emojis: List[discord.Emoji | str],
        toggle_emoji: Awaitable,
        emoji_button_style: discord.ButtonStyle,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.embedded_message = embedded_message
        self.react_emoji_strs = react_emoji_strs
        self.react_emojis = react_emojis

        self.is_cancelled = False
        self.is_confirmed = False

        self.offset = 5
        self.curr_page = 0

        self.navigation_buttons = [
            {"style": discord.ButtonStyle.blurple, "emoji": "⏮️", "callback": self.navigate_button_callback, "disabled": True, "value": "beginning"},
            {"style": discord.ButtonStyle.blurple, "emoji": "◀️", "callback": self.navigate_button_callback, "disabled": True, "value": "prev"},
            {"style": discord.ButtonStyle.blurple, "emoji": "▶️", "callback": self.navigate_button_callback, "disabled": False, "value": "next"},
            {"style": discord.ButtonStyle.blurple, "emoji": "⏭️", "callback": self.navigate_button_callback, "disabled": False, "value": "end"},
        ]

        self.emoji_buttons = {
            str(react_emoji_str): Button(
                value=react_emoji_str,
                emoji=self.react_emojis[idx],
                row=0,
                style=emoji_button_style,
                custom_callback=toggle_emoji,
            )
            for idx, react_emoji_str in enumerate(self.react_emoji_strs)
        }

        self.navigation_button_items = []

        self.reset_emoji_buttons()
        if len(self.react_emoji_strs) > self.offset:
            self.reset_navigation_buttons()

    def reset_emoji_buttons(self, reset: bool = False):
        if reset:
            for emoji_button in self.emoji_buttons.values():
                self.remove_item(emoji_button)

        start_idx = self.curr_page * self.offset
        end_idx = (
            start_idx + self.offset
            if (start_idx + self.offset) < len(self.react_emoji_strs)
            else len(self.react_emoji_strs)
        )

        emoji_buttons = list(self.emoji_buttons.items())[start_idx:end_idx]

        for _, emoji_button in emoji_buttons:
            self.add_item(emoji_button)

    def reset_navigation_buttons(self):
        if len(self.navigation_button_items) > 0:
            for navigation_button_item in self.navigation_button_items:
                self.remove_item(navigation_button_item)
            self.navigation_button_items = []

        self.navigation_buttons[0]["disabled"] = self.curr_page == 0
        self.navigation_buttons[1]["disabled"] = self.curr_page == 0
        self.navigation_buttons[2]["disabled"] = self.curr_page == (len(self.react_emoji_strs) // self.offset)
        self.navigation_buttons[3]["disabled"] = self.curr_page == (len(self.react_emoji_strs) // self.offset)

        for navigation_button in self.navigation_buttons:
            navigation_button_item = Button(
                style=navigation_button["style"],
                emoji=navigation_button["emoji"],
                custom_callback=navigation_button["callback"],
                disabled=navigation_button["disabled"],
                value=navigation_button["value"],
                row=1,
            )
            self.add_item(navigation_button_item)
            self.navigation_button_items.append(navigation_button_item)

    async def navigate_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.curr_page = self.curr_page = (
            0
            if button.value == "beginning"
            else self.curr_page - 1
            if button.value == "prev"
            else (self.curr_page + self.offset) // self.offset
            if button.value == "next"
            else len(self.react_emoji_strs) - self.offset
        )
        self.reset_emoji_buttons(reset=True)

        await asyncio.gather(self.embedded_message.edit(view=self), interaction.response.defer())

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green, emoji="✅", row=3)
    async def confirm(self, interaction: discord.Interaction, *_):
        await interaction.response.defer()
        self.is_confirmed = True
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, emoji="❌", row=3)
    async def cancel(self, interaction: discord.Interaction, *_):
        await interaction.response.defer()
        self.is_cancelled = True
        self.stop()

class EditReactEmojiOrderView(NavigateReactEmojiView):
    def __init__(
        self,
        embedded_message: Union[discord.Message, discord.InteractionMessage],
        react_emoji_strs: List[str | int],
        react_emojis: List[discord.Emoji | str],
        *args,
        **kwargs,
    ):
        super().__init__(embedded_message=embedded_message, react_emoji_strs=react_emoji_strs, react_emojis=react_emojis, toggle_emoji=self.toggle_emoji, emoji_button_style=discord.ButtonStyle.grey, *args, **kwargs)

        self.react_emoji_strs_order = []

    async def toggle_emoji(self, interaction: discord.Interaction, button: discord.ui.Button):
        if button.value in self.react_emoji_strs_order:
            self.react_emoji_strs_order.remove(button.value)
            button.style = discord.ButtonStyle.grey
        else:
            self.react_emoji_strs_order.append(button.value)
            button.style = discord.ButtonStyle.green
        
        for emoji_button in self.emoji_buttons.values():
            self.remove_item(emoji_button)

        self.emoji_buttons[str(button.value)] = button
        self.reset_emoji_buttons()

        await asyncio.gather(
            self.embedded_message.edit(
                embed=ReplaceReactEmojiViewEmbed(
                    interaction=interaction,
                    react_emojis=[
                        self.react_emojis[self.react_emoji_strs.index(react_emoji_str)]
                        for react_emoji_str in self.react_emoji_strs_order
                    ],
                ),
                view=self,
            ),
            interaction.response.defer(),
        )

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green, emoji="✅", row=3)
    async def confirm(self, interaction: discord.Interaction, *_):
        if len(self.react_emoji_strs_order) != len(self.react_emoji_strs):
            return await interaction.response.send_message(content="Please order all react emojis", ephemeral=True)

        await interaction.response.defer()
        self.is_confirmed = True
        self.stop()

class EditChannelEventDetailsView(NavigateReactEmojiView):
    def __init__(
        self,
        channel_event: dict,
        embedded_message: Union[discord.Message, discord.InteractionMessage],
        react_emojis: List[discord.Emoji | str],
        *args,
        **kwargs,
    ):
        super().__init__(embedded_message=embedded_message, react_emoji_strs=channel_event["react_emojis"], react_emojis=react_emojis, toggle_emoji=self.toggle_emoji, emoji_button_style=discord.ButtonStyle.green, *args, **kwargs)

        self.channel_event = channel_event
        self.enabled_react_emojis = self.react_emoji_strs.copy()

        self.add_item(
            Button(
                label="Ordered" if self.channel_event["ordered"] else "Unordered",
                style=discord.ButtonStyle.primary if self.channel_event["ordered"] else discord.ButtonStyle.grey,
                emoji="🔢" if self.channel_event["ordered"] else "🎲",
                row=2,
                custom_callback=self.toggle_ordered,
            )
        )

    def get_react_emojis(self):
        return [self.react_emojis[self.react_emoji_strs.index(react_emoji_str)] for react_emoji_str in self.enabled_react_emojis]

    async def toggle_emoji(self, interaction: discord.Interaction, button: discord.ui.Button):
        if button.value in self.enabled_react_emojis:
            self.enabled_react_emojis.remove(button.value)
            button.style = discord.ButtonStyle.grey
        else:
            self.enabled_react_emojis.append(button.value)
            button.style = discord.ButtonStyle.green

        for emoji_button in self.emoji_buttons.values():
            self.remove_item(emoji_button)

        self.emoji_buttons[str(button.value)] = button
        self.reset_emoji_buttons()

        await asyncio.gather(
            self.embedded_message.edit(
                embed=ChannelEventDetailsEmbed(
                    interaction=interaction, react_emojis=self.get_react_emojis(), ordered=self.channel_event["ordered"]
                ),
                view=self,
            ),
            interaction.response.defer(),
        )

    async def get_react_emoji_order(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            embed=ReplaceReactEmojiViewEmbed(interaction=interaction, react_emojis=[])
        )

        embedded_message = await interaction.original_response()
        edit_react_emoji_order_view = EditReactEmojiOrderView(
            timeout=180,
            embedded_message=embedded_message,
            react_emoji_strs=self.enabled_react_emojis,
            react_emojis=self.get_react_emojis(),
        )

        await interaction.edit_original_response(view=edit_react_emoji_order_view)

        timeout = await edit_react_emoji_order_view.wait()

        if timeout or edit_react_emoji_order_view.is_cancelled:
            await send_or_edit_interaction_message(
                interaction=interaction, edit_original_response=True, content="Timeout so no change made"
            )
            return None
        else:
            await interaction.delete_original_response()
            return edit_react_emoji_order_view.react_emoji_strs_order

    async def toggle_ordered(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.channel_event["ordered"]:
            react_emoji_order = await self.get_react_emoji_order(interaction=interaction)

            if not react_emoji_order:
                return

            self.enabled_react_emojis = react_emoji_order
            self.channel_event["react_emojis"] = react_emoji_order

            await self.embedded_message.edit(
                embed=ChannelEventDetailsEmbed(
                    interaction=interaction,
                    react_emojis=self.get_react_emojis(),
                    ordered=self.channel_event["ordered"],
                )
            )
        else:
            await interaction.response.defer()

        self.channel_event["ordered"] = not self.channel_event["ordered"]

        button.emoji = "🔢" if self.channel_event["ordered"] else "🎲"
        button.label = "Ordered" if self.channel_event["ordered"] else "Unordered"
        button.style = discord.ButtonStyle.primary if self.channel_event["ordered"] else discord.ButtonStyle.grey

        self.remove_item(button)
        self.add_item(button)

        await asyncio.gather(self.embedded_message.edit(view=self))
