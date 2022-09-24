from typing import Any, Literal, Optional, Union
import discord

from src.utils.helper import dict_has_key
from src.utils.ui import Dropdown, Button, Modal, View
from src.utils.config import RolePickerConfig

rp_conf = RolePickerConfig()


class RoleCategoryModal(Modal):
    def __init__(self, *, title: str, timeout: Optional[float] = None, custom_id: Optional[str] = None, defaults: Optional[dict] = None) -> None:
        super().__init__(title=title, timeout=timeout, custom_id=custom_id)

        self.add_item(discord.ui.TextInput(
            label='Name',
            placeholder='Enter category name',
            custom_id="label",
            default=defaults["label"] if defaults is not None else None
        ))
        
        self.add_item(discord.ui.TextInput(
            label='Description',
            placeholder='Enter description',
            style=discord.TextStyle.long,
            required=False,
            max_length=300,
            custom_id="description",
            default=defaults["description"] if defaults is not None and dict_has_key(defaults, "description") else None
        ))


class RoleModal(Modal):
    def __init__(self, *, title: str, timeout: Optional[float] = None, custom_id: Optional[str] = None, defaults: Optional[dict] = None) -> None:
        super().__init__(title=title, timeout=timeout, custom_id=custom_id)

        self.add_item(discord.ui.TextInput(
            label='Role ID',
            placeholder='Enter role ID',
            custom_id='id',
            default=defaults["id"] if defaults is not None else None
        ))
    
        self.add_item(discord.ui.TextInput(
            label='Role Label',
            placeholder='Enter role label (if no label is provided, the role name is taken)',
            required=False,
            custom_id='label',
            default=defaults["label"] if defaults is not None else None
        ))

        self.add_item(discord.ui.TextInput(
            label='Role Description',
            placeholder='Enter role description',
            style=discord.TextStyle.long,
            required=False,
            max_length=100,
            custom_id='description',
            default=defaults["description"] if defaults is not None and dict_has_key(defaults, "description") else None
        ))

        self.add_item(discord.ui.TextInput(
            label='Emoji ID',
            placeholder='Enter emoji ID',
            required=False,
            custom_id='emoji',
            default=defaults["emoji"] if defaults is not None and dict_has_key(defaults, "emoji") else None
        ))


class RoleCategoryView(View):
    def __init__(self, *, timeout: Optional[float] = None, input_type: Literal["button", "select"] = "button", max_value_type: Literal["single", "multiple"] = "multiple"):
        super().__init__(timeout=timeout)

        if input_type == "button":
            for category in rp_conf.role_categories:
                self.add_item(Button(label=category["label"], value=category["name"], custom_id=category["name"]))
        else:
            options = rp_conf.generate_role_category_options()
            self.add_item(Dropdown(
                min_values = 1, 
                max_values = len(options) if max_value_type == "multiple" else 1,
                options = options,
                placeholder="Choose categories to add the role to"
            ))


class RolesView(View):
    def __init__(self, *, timeout: Optional[float] = None, role_category: str, max_value_type: Literal["single", "multiple"] = "multiple", defaults: Optional[list] = None):
        super().__init__(timeout=timeout)

        options = rp_conf.generate_role_options(role_category, defaults=defaults)

        self.add_item(Dropdown(
            min_values = 1,
            max_values = len(options) if max_value_type == "multiple" else 1,
            options = options,
            placeholder = "Choose the roles to remove",
            row=1
        ))

        self.is_confirmed = True

    
    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green, custom_id="confirm", emoji='✔', row=2)
    async def confirm(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.is_confirmed = True
        self.stop()

    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, custom_id="cancel", emoji='✖️', row=2)
    async def cancel(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.is_confirmed = False
        self.stop()


class RolesOverviewView(View):
    def __init__(self, *, timeout: Optional[float] = None, embeds):
        super().__init__(timeout=timeout)
        self.embeds = embeds
        self.curr_idx = 0


    def update_curr_idx(self, increment):
        if self.curr_idx + increment == len(self.embeds):
            self.curr_idx = 0
        elif self.curr_idx + increment < 0:
            self.curr_idx = len(self.embeds) - 1
        else:
            self.curr_idx = self.curr_idx + increment
        
        return self.curr_idx


    @discord.ui.button(label='Previous', style=discord.ButtonStyle.primary, custom_id="prev", emoji='⬅️')
    async def cancel(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.value = False
        await interaction.response.edit_message(embed=self.embeds[self.update_curr_idx(-1)])
    
    
    @discord.ui.button(label='Next', style=discord.ButtonStyle.primary, custom_id="next", emoji='➡️')
    async def confirm(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.value = True
        await interaction.response.edit_message(embed=self.embeds[self.update_curr_idx(1)])

    
    @discord.ui.button(style=discord.ButtonStyle.red, custom_id="lock", emoji='🔒')
    async def lock(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.stop()
        await interaction.response.edit_message(view=None)


class PersistentRolesButton(discord.ui.Button):
    def __init__(self, *, style: discord.ButtonStyle = discord.ButtonStyle.primary, label: Optional[str] = None, disabled: bool = False, custom_id: Optional[str] = None, url: Optional[str] = None, emoji: Optional[Union[str, discord.Emoji, discord.PartialEmoji]] = None, row: Optional[int] = None, value: Optional[Any] = None):
        super().__init__(style=style, label=label, disabled=disabled, custom_id=custom_id, url=url, emoji=emoji, row=row)
        self.value = value

    
    async def callback(self, interaction: discord.Interaction):
        user_role_ids = [role.id for role in interaction.user.roles]
        role_category = self.value

        roles_view = RolesView(role_category=role_category, timeout=90, defaults=user_role_ids)
        await interaction.response.send_message(content="Select roles!", view=roles_view, ephemeral=True)
        await roles_view.wait()

        if roles_view.is_confirmed and roles_view.values is not None:
            selected_role_ids = [int(role_id) for role_id in roles_view.values]
            common_current_role_ids = list(set(user_role_ids).intersection(set(rp_conf.get_role_ids(role_category))))
            common_selected_role_ids = list(set(selected_role_ids).intersection(set(user_role_ids)))
            
            role_ids_to_add = [int(role_id) for role_id in selected_role_ids if role_id not in common_selected_role_ids]
            role_ids_to_del = [int(role_id) for role_id in common_current_role_ids if role_id not in common_selected_role_ids]

            for role_id in role_ids_to_add:
                role = interaction.guild.get_role(int(role_id))
                await interaction.user.add_roles(role)

            for role_id in role_ids_to_del:
                role = interaction.guild.get_role(int(role_id))
                await interaction.user.remove_roles(role)

            await interaction.edit_original_response(content="Your roles have been successfully changed!", view=None)
        else:
            await interaction.edit_original_response(content="Your roles were not changed!", view=None)
        


class PersistentRolesView(View):
    def __init__(self, *, timeout: Optional[float] = None):
        super().__init__(timeout=timeout)

        for category in rp_conf.role_categories:
            self.add_item(PersistentRolesButton(label=category["label"], value=category["name"], custom_id=f"persistent:{category['name']}"))
