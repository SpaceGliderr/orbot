import asyncio
from typing import Any, List, Literal, Optional, Union

import discord

from src.modules.ui.common import Button, Modal, Select, View
from src.utils.config import RolePickerConfig
from src.utils.helper import dict_has_key


# =================================================================================================================
# ROLE PICKER MODALS
# =================================================================================================================
class RoleCategoryModal(Modal):
    """Creates a modal popup window to add or edit a Role Category by inheriting the `Modal` class.

    Has 2 text inputs for `label` and `description`.

    Additional Parameters
    ----------
        * defaults: Optional[:class:`dict`]
            - Fills the default values for each text input. Possible keys: `label`, `description`.
    """

    def __init__(self, defaults: Optional[dict] = None, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.add_item(
            discord.ui.TextInput(
                label="Name",
                placeholder="Enter category name",
                custom_id="label",
                default=defaults["label"] if defaults is not None else None,
            )
        )

        self.add_item(
            discord.ui.TextInput(
                label="Number of Selectable Roles",
                placeholder="Enter 'Single' or 'Multiple'",
                custom_id="limit",
                default=defaults["limit"] if defaults is not None else "Multiple",
            )
        )

        self.add_item(
            discord.ui.TextInput(
                label="Description",
                placeholder="Enter description",
                style=discord.TextStyle.long,
                required=False,
                custom_id="description",
                default=defaults["description"]
                if defaults is not None and dict_has_key(defaults, "description")
                else None,
            )
        )


class RoleModal(Modal):
    """Creates a modal popup window to add or edit a Role by inheriting the `Modal` class.

    Has 4 text inputs for `id`, `label`, `description` and `emoji`.

    Additional Parameters
    ----------
        * defaults: Optional[:class:`dict`]
            - Fills the default values for each text input. Possible keys: `id`, `label`, `description`, `emoji`.
    """

    def __init__(self, defaults: Optional[dict] = None, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.add_item(
            discord.ui.TextInput(
                label="Role ID",
                placeholder="Enter role ID",
                custom_id="id",
                default=defaults["id"] if defaults is not None else None,
            )
        )

        self.add_item(
            discord.ui.TextInput(
                label="Role Label",
                placeholder="Enter role label (defaults to role name)",
                required=False,
                custom_id="label",
                default=defaults["label"] if defaults is not None else None,
            )
        )

        self.add_item(
            discord.ui.TextInput(
                label="Role Description",
                placeholder="Enter role description",
                style=discord.TextStyle.long,
                required=False,
                custom_id="description",
                default=defaults["description"]
                if defaults is not None and dict_has_key(defaults, "description")
                else None,
            )
        )

        self.add_item(
            discord.ui.TextInput(
                label="Emoji ID",
                placeholder="Enter emoji ID",
                required=False,
                custom_id="emoji",
                default=defaults["emoji"] if defaults is not None and dict_has_key(defaults, "emoji") else None,
            )
        )


# =================================================================================================================
# ROLE PICKER VIEWS
# =================================================================================================================
class RoleCategoryView(View):
    """Creates a view to select Role Category(ies) by inheriting the `View` class.

    Additional Parameters
    ----------
        * input_type: Literal[`button`, `select`] | `button`
            - Controls the input type of the view, either displays buttons or a select menu.
        * max_value_type: Literal[`single`, `multiple`] | `multiple`
            - Controls the number of maximum values for the select menu. The `multiple` option takes the total number of options as the maximum selectable values in the select menu.
    """

    def __init__(
        self,
        input_type: Literal["button", "select"] = "button",
        max_value_type: Literal["single", "multiple"] = "multiple",
        stop_view: bool = False,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        rp_conf = RolePickerConfig()

        if input_type == "button":
            for category in rp_conf.role_categories:
                self.add_item(
                    Button(
                        label=category["label"],
                        value=category["name"],
                        stop_view=stop_view,
                        style=discord.ButtonStyle.primary,
                    )
                )
        else:
            options = rp_conf.generate_role_category_options()
            self.add_item(
                Select(
                    min_values=1,
                    max_values=len(options) if max_value_type == "multiple" else 1,
                    options=options,
                    placeholder="Choose role categories",
                    stop_view=stop_view,
                )
            )


class RolesView(View):
    """Creates a view to select Role(s) by inheriting the `View` class.

    Has a select menu, confirm and cancel buttons.

    Additional Parameters
    ----------
        * min_values: :class:`int` | `1`
            - Minimum number of selectable items in the select menu.
        * role_category: :class:`str`
            - The role category to extract the list of roles from.
        * defaults: Optional[:class:`list`]
            - Automatically selects the default roles for the select menu.
        * max_value_type: Literal[`single`, `multiple`] | `multiple`
            - Controls the number of maximum values for the select menu. The `multiple` option takes the total number of options as the maximum selectable values in the select menu.
    """

    def __init__(
        self,
        role_category: str,
        min_values: int = 1,
        max_value_type: Literal["single", "multiple"] = "multiple",
        defaults: Optional[list] = None,
        stop_view: bool = False,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        rp_conf = RolePickerConfig()
        filtered_defaults = list(set(defaults).intersection(set(rp_conf.get_role_ids(role_category))))

        # TODO: This is just a temp fix for the discord caching bug
        if len(filtered_defaults) == 0:
            filtered_defaults = None
        elif max_value_type == "single":
            filtered_defaults = [filtered_defaults[0]]

        options = rp_conf.generate_role_options(role_category, defaults=filtered_defaults)

        self.add_item(
            Select(
                min_values=min_values,
                max_values=len(options) if max_value_type == "multiple" else 1,
                options=options,
                placeholder="Choose multiple roles" if max_value_type == "multiple" else "Choose a role",
                row=1,
                stop_view=stop_view,
                defer=True,
            )
        )

        self.is_confirmed = True

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green, emoji="✔", row=2)
    async def confirm(self, interaction: discord.Interaction, *_):
        self.is_confirmed = True
        self.interaction = interaction
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, emoji="✖️", row=2)
    async def cancel(self, interaction: discord.Interaction, *_):
        self.is_confirmed = False
        self.interaction = interaction
        self.stop()


class RolesOverviewView(View):
    """Creates an overview of the role categories and roles with embeds by inheriting the `View` class.

    Has previous, next and lock buttons.

    Additional Parameters
    ----------
        * embeds: :class:`list`
            - List of embeds to iterate through.
    """

    def __init__(self, *, timeout: Optional[float] = None, embeds: List[discord.Embed]):
        super().__init__(timeout=timeout)
        self.embeds = embeds
        self.curr_idx = 0

    def update_curr_idx(self, increment):
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


# =================================================================================================================
# ROLE PICKER PERSISTENT ITEMS AND VIEWS
# =================================================================================================================
class PersistentRoleCategoryButton(discord.ui.Button):
    """Creates a persistent button by inheriting the `discord.ui.Button` class.

    Has a custom callback to send an ephemeral RolesView view to add / remove roles from the user that interacts with it.

    Additional Parameters and Attributes
    ----------
        * value: :class:`Any`
            - The value that the button holds.
    """

    def __init__(self, value: Any, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.value = value

    async def callback(self, interaction: discord.Interaction):
        rp_conf = RolePickerConfig()

        user_role_ids = [role.id for role in interaction.user.roles]
        role_category = self.value

        # Send RolesView
        roles_view = RolesView(
            role_category=role_category,
            timeout=90,
            defaults=user_role_ids,
            min_values=0,
            max_value_type=rp_conf.get_role_category(role_category)[1]["limit"],
        )
        await interaction.response.send_message(
            content=f"Select your roles from the {rp_conf.get_role_category(role_category)[1]['label']} category!",
            view=roles_view,
            ephemeral=True,
        )

        timeout = await roles_view.wait()

        if timeout:
            await interaction.edit_original_response(
                content="The role picker has timed out, please click on a category again!", view=None
            )
            return

        await roles_view.interaction.response.defer()

        if roles_view.is_confirmed and roles_view.ret_val is not None:
            selected_role_ids = [int(role_id) for role_id in roles_view.ret_val]  # The selected role IDs
            common_current_role_ids = list(
                set(user_role_ids).intersection(set(rp_conf.get_role_ids(role_category)))
            )  # The same previous user role IDs compared to the selected category role IDs

            if set(selected_role_ids) != set(common_current_role_ids):
                await interaction.edit_original_response(content="Changing your roles...", view=None)

                common_selected_role_ids = list(
                    set(selected_role_ids).intersection(set(user_role_ids))
                )  # The same selected role IDs compared to the previous user role IDs

                # Filter out role IDs to add and delete
                roles_to_add = [
                    interaction.guild.get_role(int(role_id))
                    for role_id in selected_role_ids
                    if role_id not in common_selected_role_ids
                ]
                roles_to_del = [
                    interaction.guild.get_role(int(role_id))
                    for role_id in common_current_role_ids
                    if role_id not in common_selected_role_ids
                ]

                # Add / Remove roles
                await asyncio.gather(
                    interaction.user.add_roles(*roles_to_add), interaction.user.remove_roles(*roles_to_del)
                )

                await interaction.edit_original_response(
                    content="Your roles have been successfully changed!", view=None
                )
            else:
                await interaction.edit_original_response(content="Your roles were not changed!", view=None)
        else:
            await interaction.edit_original_response(content="Your roles were not changed!", view=None)


class PersistentRolePickerView(View):
    """Creates a persistent role picker view by inheriting the `View` class.

    Sets up a list of PersistentRoleCategoryButton and a listener.
    """

    def __init__(self, *, timeout: Optional[float] = None):
        super().__init__(timeout=timeout)

        rp_conf = RolePickerConfig()

        for category in rp_conf.role_categories:
            if rp_conf.get_roles(category["name"]) is not None:  # Not supposed to show categories with empty roles
                self.add_item(
                    PersistentRoleCategoryButton(
                        label=category["label"],
                        value=category["name"],
                        custom_id=f"persistent:{category['name']}",
                        style=discord.ButtonStyle.primary,
                    )
                )
