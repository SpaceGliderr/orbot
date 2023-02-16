import asyncio
from typing import Awaitable, List, Literal, Optional, Union

import discord

from src.modules.ui.common import Button, View
from src.utils.helper import send_or_edit_interaction_message


class ChannelEventsEmbed(discord.Embed):
    """Creates an embed that renders a list of thread event details under a thread event by inheriting the `discord.Embed` class.

    Parameters
    ----------
        * thread_events: List[:class:`tuple`]
            - The thread events to render in the embed fields.
        * guild: :class:`discord.Guild`
        * event_types: List[:class:str]
            - The event types of the thread events (only applicable if the channel is selected as a filter).
        * channel_id: Optional[:class:int] | None
            - Used to generate the embed description.
        * event_type: Optional[:class:`Literal["on_thread_create", "on_thread_update"]`] | None
            - Used to generate the embed description.
    """

    @classmethod
    async def init(
        cls,
        thread_events: List[tuple],
        guild: discord.Guild,
        event_types: List[str],
        channel_id: Optional[int] = None,
        event_type: Optional[Literal["on_thread_create", "on_thread_update"]] = None,
        *args,
        **kwargs,
    ):
        embed = cls(
            title="List of Thread Events",
            description="{channel_id}{newline}{event_type}".format(
                channel_id=f"**Channel:** <#{channel_id}>" if channel_id else "",
                newline="\n" if channel_id and event_type else "",
                event_type=f"**Event Type:** `{event_type}`" if event_type else "",
            )
            if channel_id or event_type
            else "Shows all the thread events for the server.",
            *args,
            **kwargs,
        )

        for idx, (thread_event_channel_id, thread_event) in enumerate(thread_events):
            react_emojis = [await guild.fetch_emoji(emoji) if isinstance(emoji, int) else emoji for emoji in thread_event["react_emojis"]]

            embed.add_field(
                name=f"`{event_types[idx]}`" if channel_id else f"<#{thread_event_channel_id}>",
                value=f"**Reactions:** {', '.join([str(react_emoji) for react_emoji in react_emojis])}\n**Ordered:** {'Yes' if thread_event['ordered'] else 'No'}",
                inline=False
            )

        return embed


class ReactEmojiEmbed(discord.Embed):
    """Creates an embed that renders the Discord emojis by inheriting the `discord.Embed` class.

    Parameters
    ----------
        * interaction: :class:`discord.Interaction`
            - Used to set the author of the embed.
        * react_emojis: List[:class:`discord.Emoji`, :class:`str`]
            - List of Discord emojis to render in the embed.
    """

    def __init__(
        self,
        interaction: discord.Interaction,
        react_emojis: List[discord.Emoji | str],
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.set_author(name=interaction.user.display_name, icon_url=interaction.user.avatar)
        self.add_field(
            name="Reactions",
            value=", ".join([str(react_emoji) for react_emoji in react_emojis])
            if len(react_emojis) > 0
            else "_<No emojis selected>_",
            inline=False,
        )


class ChannelEventDetailsEmbed(ReactEmojiEmbed):
    """Creates an embed that shows the Channel Event details by inheriting the `ReactEmojiEmbed` class. The `ReactEmojiEmbed` will display the emoji information.

    Parameters
    ----------
        * interaction: :class:`discord.Interaction`
        * react_emojis: List[:class:`discord.Emoji`, :class:`str`]
        * ordered: :class:`bool`
            - Whether the reactions should be added in order or not.
    """

    def __init__(
        self, interaction: discord.Interaction, react_emojis: List[discord.Emoji | str], ordered: bool, *args, **kwargs
    ):
        super().__init__(interaction=interaction, react_emojis=react_emojis, *args, **kwargs)

        self.title = "Channel Event Details"
        self.add_field(name="Ordered", value="Yes" if ordered else "No", inline=False)


class ReplaceReactEmojiView(View):
    """Creates a view that allows users to confirm whether they want to replace or add onto existing emojis by inheriting the `View` class."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.replace = False
        self.is_cancelled = False

    # =================================================================================================================
    # BUTTON CALLBACKS
    # =================================================================================================================
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
    """Creates an view that allows users to navigate through a list of Discord emojis by inheriting the `View` class. Users can also toggle the emoji buttons on or off with different responses based on the `toggle_emoji` callback provided.

    Parameters
    ----------
        * embedded_message: Union[:class:`discord.Message`, :class:`discord.InteractionMessage`]
            - The message to edit with the updated view.
        * react_emoji_strs: List[:class:`str` | :class:`int`]
            - A list of react emoji strings or integers. Strings are unicode emojis and integers signifies Discord emojis.
        * react_emojis: List[:class:`discord.Emoji`, :class:`str`]
            - A list of `discord.Emoji` emoji objects or unicode emoji strings.
        * toggle_emoji: Optional[:class:`Awaitable`]
            - An optional callback to control how the the emoji buttons responds on click. If no toggle emoji button is provided, the button will be disabled.
        * emoji_button_style: :class:`discord.ButtonStyle`
            - Whether the reactions should be added in order or not.
    """

    def __init__(
        self,
        embedded_message: Union[discord.Message, discord.InteractionMessage],
        react_emoji_strs: List[str | int],
        react_emojis: List[discord.Emoji | str],
        emoji_button_style: discord.ButtonStyle,
        toggle_emoji: Optional[Awaitable] = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.embedded_message = embedded_message
        self.react_emoji_strs = react_emoji_strs
        self.react_emojis = react_emojis

        # Variables to check whether operation is confirmed or cancelled
        self.is_cancelled = False
        self.is_confirmed = False

        # Instance variables to keep track of emoji button pagination
        self.offset = 5
        self.curr_page = 0

        self.navigation_buttons = [
            {
                "style": discord.ButtonStyle.blurple,
                "emoji": "⏮️",
                "callback": self.navigate_button_callback,
                "disabled": True,
                "value": "beginning",
            },
            {
                "style": discord.ButtonStyle.blurple,
                "emoji": "◀️",
                "callback": self.navigate_button_callback,
                "disabled": True,
                "value": "prev",
            },
            {
                "style": discord.ButtonStyle.blurple,
                "emoji": "▶️",
                "callback": self.navigate_button_callback,
                "disabled": False,
                "value": "next",
            },
            {
                "style": discord.ButtonStyle.blurple,
                "emoji": "⏭️",
                "callback": self.navigate_button_callback,
                "disabled": False,
                "value": "end",
            },
        ]

        self.emoji_buttons = {
            str(react_emoji_str): Button(
                value=react_emoji_str,
                emoji=self.react_emojis[idx],
                row=0,
                style=emoji_button_style,
                custom_callback=toggle_emoji,
                disabled=toggle_emoji is None,
            )
            for idx, react_emoji_str in enumerate(self.react_emoji_strs)
        }

        self.navigation_button_items = (
            []
        )  # List that keeps track of the navigation button `Button` objects to be removed from the view when the navigation buttons are reset

        # Initialize the emoji buttons and navigation buttons
        self.reset_emoji_buttons()
        if len(self.react_emoji_strs) > self.offset:  # Display navigation buttons only if there are >5 emoji buttons
            self.reset_navigation_buttons()

    # =================================================================================================================
    # VIEW FUNCTIONS
    # =================================================================================================================
    def reset_emoji_buttons(self, reset: bool = False):
        """A method that sets or replaces emoji buttons.

        Parameters
        ----------
            * reset: :class:`bool`
                - Set to `True` when all emoji buttons in `self.emoji_buttons` has been initialized in the view to remove the old buttons and replace it with new buttons.
        """
        if reset:  # Remove old emoji buttons from the view
            for emoji_button in self.emoji_buttons.values():
                self.remove_item(emoji_button)

        # Calculate the pagination indexes
        start_idx = self.curr_page * self.offset
        end_idx = (
            start_idx + self.offset
            if (start_idx + self.offset) < len(self.react_emoji_strs)
            else len(self.react_emoji_strs)
        )

        # Obtain the range of emoji buttons from the `self.emoji_buttons` dictionary and add the `Button` object to the view
        emoji_buttons = list(self.emoji_buttons.items())[start_idx:end_idx]
        for _, emoji_button in emoji_buttons:
            self.add_item(emoji_button)

    def reset_navigation_buttons(self):
        """A method that sets or replaces navigation buttons."""
        if (
            len(self.navigation_button_items) > 0
        ):  # Check whether the navigation buttons have been initialized. If so, remove the initialized navigation buttons
            for navigation_button_item in self.navigation_button_items:
                self.remove_item(navigation_button_item)
            self.navigation_button_items = []

        # Set the `disabled` attribute for the navigation buttons
        self.navigation_buttons[0]["disabled"] = self.curr_page == 0  # `beginning` button
        self.navigation_buttons[1]["disabled"] = self.curr_page == 0  # `previous` button
        self.navigation_buttons[2]["disabled"] = self.curr_page == (
            len(self.react_emoji_strs) // self.offset
        )  # `next` button
        self.navigation_buttons[3]["disabled"] = self.curr_page == (
            len(self.react_emoji_strs) // self.offset
        )  # `end` button

        for navigation_button in self.navigation_buttons:  # Create the `Button` objects and add them to the view
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

    # =================================================================================================================
    # BUTTON CALLBACKS
    # =================================================================================================================
    async def navigate_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        """A callback that is used by the navigation buttons."""
        self.curr_page = self.curr_page = (
            0
            if button.value == "beginning"
            else self.curr_page - 1
            if button.value == "prev"
            else (self.curr_page + self.offset) // self.offset
            if button.value == "next"
            else len(self.react_emoji_strs) - self.offset
        )  # Determines the current page variable
        self.reset_emoji_buttons(reset=True)

        await asyncio.gather(
            self.embedded_message.edit(view=self), interaction.response.defer()
        )  # Updates the embedded message with the updated view

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
    """Creates an view that allows users to rearrange the order of a list of Discord emojis by inheriting the `NavigateReactEmojiView` class.

    Parameters
    ----------
        * embedded_message: Union[:class:`discord.Message`, :class:`discord.InteractionMessage`]
            - The message to edit with the updated view.
        * react_emoji_strs: List[:class:`str` | :class:`int`]
            - A list of react emoji strings or integers. Strings are unicode emojis and integers signifies Discord emojis.
        * react_emojis: List[:class:`discord.Emoji`, :class:`str`]
            - A list of `discord.Emoji` emoji objects or unicode emoji strings.
    """

    def __init__(
        self,
        embedded_message: Union[discord.Message, discord.InteractionMessage],
        react_emoji_strs: List[str | int],
        react_emojis: List[discord.Emoji | str],
        *args,
        **kwargs,
    ):
        super().__init__(
            embedded_message=embedded_message,
            react_emoji_strs=react_emoji_strs,
            react_emojis=react_emojis,
            emoji_button_style=discord.ButtonStyle.grey,
            toggle_emoji=self.toggle_emoji,
            *args,
            **kwargs,
        )

        self.react_emoji_strs_order = []  # Variable to store the new order of emojis

    # =================================================================================================================
    # BUTTON CALLBACKS
    # =================================================================================================================
    async def toggle_emoji(self, interaction: discord.Interaction, button: discord.ui.Button):
        """A method that allows users to select and deselect emojis, rearranging the emoji order based on the order selected."""
        # Adds or removes the emoji from the order list and update emoji button object
        if button.value in self.react_emoji_strs_order:
            self.react_emoji_strs_order.remove(button.value)
            button.style = discord.ButtonStyle.grey
        else:
            self.react_emoji_strs_order.append(button.value)
            button.style = discord.ButtonStyle.green

        # Remove emoji buttons
        for emoji_button in self.emoji_buttons.values():
            self.remove_item(emoji_button)

        # Update the `emoji_buttons` dictionary with the updated button object and update the view
        self.emoji_buttons[str(button.value)] = button
        self.reset_emoji_buttons()

        # Edit the embedded message with the updated view
        await asyncio.gather(
            self.embedded_message.edit(
                embed=ReactEmojiEmbed(
                    title="Edit React Emoji Order",
                    description="Click on the emojis to rearrange the order of the emojis. Ensure that all emojis have been selected before confirming.",
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
        if len(self.react_emoji_strs_order) != len(
            self.react_emoji_strs
        ):  # Ensure that all emojis are selected before ending the interaction
            return await interaction.response.send_message(
                content="Please ensure all react emojis are selected before confirming.", ephemeral=True
            )

        await interaction.response.defer()
        self.is_confirmed = True
        self.stop()


class EditChannelEventDetailsView(NavigateReactEmojiView):
    """Creates an view that allows users to choose which emojis to keep or discard from a list of Discord emojis by inheriting the `NavigateReactEmojiView` class.

    Parameters
    ----------
        * embedded_message: Union[:class:`discord.Message`, :class:`discord.InteractionMessage`]
            - The message to edit with the updated view.
        * react_emoji_strs: List[:class:`str` | :class:`int`]
            - A list of react emoji strings or integers. Strings are unicode emojis and integers signifies Discord emojis.
        * react_emojis: List[:class:`discord.Emoji`, :class:`str`]
            - A list of `discord.Emoji` emoji objects or unicode emoji strings.
        * interaction_user: Union[:class:`discord.User`, :class:`discord.Member`]
            - The user that is allowed to interact with this `View`.
    """

    def __init__(
        self,
        thread_event: dict,
        embedded_message: Union[discord.Message, discord.InteractionMessage],
        react_emojis: List[discord.Emoji | str],
        interaction_user: Union[discord.User, discord.Member],
        *args,
        **kwargs,
    ):
        super().__init__(
            embedded_message=embedded_message,
            react_emoji_strs=thread_event["react_emojis"],
            react_emojis=react_emojis,
            emoji_button_style=discord.ButtonStyle.green,
            toggle_emoji=self.toggle_emoji,
            *args,
            **kwargs,
        )

        self.is_order_view_active = False

        self.thread_event = thread_event
        self.enabled_react_emojis = (
            self.react_emoji_strs.copy()
        )  # Copy the list of emoji strings to avoid manipulating the contents of the original list
        self.interaction_user = interaction_user

        self.add_item(
            Button(
                label="Ordered" if self.thread_event["ordered"] else "Unordered",
                style=discord.ButtonStyle.primary if self.thread_event["ordered"] else discord.ButtonStyle.grey,
                emoji="🔢" if self.thread_event["ordered"] else "🎲",
                row=2,
                custom_callback=self.toggle_ordered,
            )
        )

    # =================================================================================================================
    # VIEW FUNCTIONS
    # =================================================================================================================
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Overrides the `interaction_check` method for `discord.View`.
        Checks whether the user that interacts with this view is equal to the `interaction_user` instance variable.
        If the user is valid, then it checks whether the user is currently rearranging the emojis. If so, it would not allow the user to interact with the buttons.
        """
        if self.interaction_user != interaction.user:
            await interaction.response.send_message(
                content="You are not allowed to interact with this post!", ephemeral=True
            )
            return False
        elif self.is_order_view_active:
            await interaction.response.send_message(
                content="Please finish rearranging the emoji order before editing the thread event details.",
                ephemeral=True,
            )
            return False
        return True

    def get_react_emojis(self):
        """A method that obtains the `discord.Emoji` objects of the chosen emojis."""
        return [
            self.react_emojis[self.react_emoji_strs.index(react_emoji_str)]
            for react_emoji_str in self.enabled_react_emojis
        ]

    async def get_react_emoji_order(self, interaction: discord.Interaction):
        """A method that sends a `EditReactEmojiOrderView` to get a new arrangement of emojis."""
        await interaction.response.send_message(
            embed=ReactEmojiEmbed(
                title="Edit React Emoji Order",
                description="Click on the emojis to rearrange the order of the emojis. Ensure that all emojis have been selected before confirming.",
                interaction=interaction,
                react_emojis=[],  # Has to be an empty array because the user would have to determine the order of emojis displayed
            )
        )
        embedded_message = await interaction.original_response()

        # Set the `EditReactEmojiOrderView` onto the embedded message
        edit_react_emoji_order_view = EditReactEmojiOrderView(
            embedded_message=embedded_message,
            react_emoji_strs=self.enabled_react_emojis,
            react_emojis=self.get_react_emojis(),
            timeout=90,
        )
        await interaction.edit_original_response(view=edit_react_emoji_order_view)

        timeout = await edit_react_emoji_order_view.wait()
        if timeout or edit_react_emoji_order_view.is_cancelled:
            await send_or_edit_interaction_message(
                interaction=interaction,
                edit_original_response=True,
                content="The command has timed out. Please try again."
                if timeout
                else "Command cancelled. No changes were made to the order of the emojis.",
            )
            return None
        else:  # Get and return the new emoji arrangement
            await interaction.delete_original_response()
            return edit_react_emoji_order_view.react_emoji_strs_order

    # =================================================================================================================
    # BUTTON CALLBACKS
    # =================================================================================================================
    async def toggle_emoji(self, interaction: discord.Interaction, button: discord.ui.Button):
        """A method that allows users to select and deselect emojis, rearranging the emoji order based on the order selected."""
        # Adds or removes the emoji from the order list and update emoji button object
        if button.value in self.enabled_react_emojis:
            self.enabled_react_emojis.remove(button.value)
            button.style = discord.ButtonStyle.grey
        else:
            self.enabled_react_emojis.append(button.value)
            button.style = discord.ButtonStyle.green

        # Remove emoji buttons
        for emoji_button in self.emoji_buttons.values():
            self.remove_item(emoji_button)

        # Update the `emoji_buttons` dictionary with the updated button object and update the view
        self.emoji_buttons[str(button.value)] = button
        self.reset_emoji_buttons()

        # Edit the embedded message with the updated view
        await asyncio.gather(
            self.embedded_message.edit(
                embed=ChannelEventDetailsEmbed(
                    interaction=interaction, react_emojis=self.get_react_emojis(), ordered=self.thread_event["ordered"]
                ),
                view=self,
            ),
            interaction.response.defer(),
        )

    async def toggle_ordered(self, interaction: discord.Interaction, button: discord.ui.Button):
        """A callback used by the Order button to control the order of the emojis."""
        if self.thread_event["ordered"]:
            await interaction.response.defer()
        else:  # Only if we are switching from Unordered -> Ordered, we need to get the new emoji arrangement
            self.is_order_view_active = True
            react_emoji_order = await self.get_react_emoji_order(interaction=interaction)

            if not react_emoji_order:  # If the view timed out or was cancelled
                self.is_order_view_active = False
                return

            # Set new emoji order and update the embed
            self.enabled_react_emojis = react_emoji_order
            await self.embedded_message.edit(
                embed=ChannelEventDetailsEmbed(
                    interaction=interaction,
                    react_emojis=self.get_react_emojis(),
                    ordered=self.thread_event["ordered"],
                )
            )
            self.is_order_view_active = (
                False  # Placed at the end to ensure that the variable and UI are updated before allowing users to edit
            )

        # Update the `ordered` variable and update the Order button
        self.thread_event["ordered"] = not self.thread_event["ordered"]

        button.emoji = "🔢" if self.thread_event["ordered"] else "🎲"
        button.label = "Ordered" if self.thread_event["ordered"] else "Unordered"
        button.style = discord.ButtonStyle.primary if self.thread_event["ordered"] else discord.ButtonStyle.grey

        self.remove_item(button)
        self.add_item(button)

        await asyncio.gather(self.embedded_message.edit(view=self))

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green, emoji="✅", row=3)
    async def confirm(self, interaction: discord.Interaction, *_):
        if len(self.enabled_react_emojis) == 0:
            return await interaction.response.send_message(
                content="Please ensure at least one react emoji is selected. If you wish to delete the channel event, use the `delete-thread-reaction-event` slash command instead.",
                ephemeral=True,
            )

        await interaction.response.defer()
        self.is_confirmed = True
        self.stop()
