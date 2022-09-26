from typing import Any, Literal, Optional, Union

import discord

from src.utils.config import RolePickerConfig
from src.utils.helper import dict_has_key
from src.utils.ui import Button, Modal, Select, View


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

    def __init__(
        self,
        *,
        title: str,
        timeout: Optional[float] = None,
        custom_id: Optional[str] = None,
        success_msg: Optional[str] = None,
        error_msg: Optional[str] = None,
        defaults: Optional[dict] = None,
    ) -> None:
        super().__init__(
            title=title, timeout=timeout, custom_id=custom_id, success_msg=success_msg, error_msg=error_msg
        )

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

    def __init__(
        self,
        *,
        title: str,
        timeout: Optional[float] = None,
        custom_id: Optional[str] = None,
        success_msg: Optional[str] = None,
        error_msg: Optional[str] = None,
        defaults: Optional[dict] = None,
    ) -> None:
        super().__init__(
            title=title, timeout=timeout, custom_id=custom_id, success_msg=success_msg, error_msg=error_msg
        )

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
        *,
        timeout: Optional[float] = None,
        input_type: Literal["button", "select"] = "button",
        max_value_type: Literal["single", "multiple"] = "multiple",
        stop_view: bool = False,
    ):
        super().__init__(timeout=timeout)

        rp_conf = RolePickerConfig()

        if input_type == "button":
            for category in rp_conf.role_categories:
                self.add_item(
                    Button(
                        label=category["label"], value=category["name"], custom_id=category["name"], stop_view=stop_view
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
                    custom_id="role_category_select",
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
        *,
        timeout: Optional[float] = None,
        min_values: int = 1,
        role_category: str,
        max_value_type: Literal["single", "multiple"] = "multiple",
        defaults: Optional[list] = None,
        stop_view: bool = False,
    ):
        super().__init__(timeout=timeout)

        rp_conf = RolePickerConfig()

        options = rp_conf.generate_role_options(role_category, defaults=defaults)

        self.add_item(
            Select(
                min_values=min_values,
                max_values=len(options) if max_value_type == "multiple" else 1,
                options=options,
                placeholder="Choose multiple roles" if max_value_type == "multiple" else "Choose a role",
                row=1,
                stop_view=stop_view,
                custom_id="roles_select",
                defer=True,
            )
        )

        self.is_confirmed = True

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green, custom_id="confirm", emoji="✔", row=2)
    async def confirm(self, interaction: discord.Interaction, *_):
        self.is_confirmed = True
        self.interaction = interaction
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, custom_id="cancel", emoji="✖️", row=2)
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

    def __init__(self, *, timeout: Optional[float] = None, embeds: list):
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

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.primary, custom_id="prev", emoji="⬅️")
    async def previous(self, interaction: discord.Interaction, *_):
        self.value = False
        await interaction.response.edit_message(embed=self.embeds[self.update_curr_idx(-1)])

    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary, custom_id="next", emoji="➡️")
    async def next(self, interaction: discord.Interaction, *_):
        self.value = True
        await interaction.response.edit_message(embed=self.embeds[self.update_curr_idx(1)])

    @discord.ui.button(style=discord.ButtonStyle.red, custom_id="lock", emoji="🔒")
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
        value: Any,
    ):
        super().__init__(
            style=style, label=label, disabled=disabled, custom_id=custom_id, url=url, emoji=emoji, row=row
        )
        self.value = value

    async def callback(self, interaction: discord.Interaction):
        rp_conf = RolePickerConfig()

        user_role_ids = [role.id for role in interaction.user.roles]
        role_category = self.value

        # Send RolesView
        roles_view = RolesView(role_category=role_category, timeout=90, defaults=user_role_ids, min_values=0)
        await interaction.response.send_message(
            content=f"Select your roles from the {rp_conf.get_role_category(role_category)[1]['label']} category!",
            view=roles_view,
            ephemeral=True,
        )
        await roles_view.wait()

        if roles_view.is_confirmed and roles_view.values is not None:
            selected_role_ids = [int(role_id) for role_id in roles_view.values]  # The selected role IDs
            common_current_role_ids = list(
                set(user_role_ids).intersection(set(rp_conf.get_role_ids(role_category)))
            )  # The same previous user role IDs compared to the selected category role IDs
            common_selected_role_ids = list(
                set(selected_role_ids).intersection(set(user_role_ids))
            )  # The same selected role IDs compared to the previous user role IDs

            # Filter out role IDs to add and delete
            role_ids_to_add = [int(role_id) for role_id in selected_role_ids if role_id not in common_selected_role_ids]
            role_ids_to_del = [
                int(role_id) for role_id in common_current_role_ids if role_id not in common_selected_role_ids
            ]

            # Add / Remove roles
            for role_id in role_ids_to_add:
                role = interaction.guild.get_role(int(role_id))
                await interaction.user.add_roles(role)

            for role_id in role_ids_to_del:
                role = interaction.guild.get_role(int(role_id))
                await interaction.user.remove_roles(role)

            await interaction.edit_original_response(content="Your roles have been successfully changed!", view=None)
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
            if rp_conf.get_roles(category["name"]) is not None: # Not supposed to show categories with empty roles
                self.add_item(
                    PersistentRoleCategoryButton(
                        label=category["label"], value=category["name"], custom_id=f"persistent:{category['name']}"
                    )
                )
