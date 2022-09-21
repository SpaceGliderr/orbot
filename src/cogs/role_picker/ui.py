from typing import Literal, Optional
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
    def __init__(self, *, timeout: Optional[float] = None, input_type: Literal["button", "select"] = "button", max_value_type: Literal["single", "multiple"] = "multiple", is_delete: bool = False):
        super().__init__(timeout=timeout)

        if input_type == "button":
            for category in rp_conf.role_categories:
                self.add_item(Button(label=category["label"], value=category["name"]))
        else:
            options = rp_conf.generate_role_category_options(is_delete=is_delete)
            self.add_item(Dropdown(
                min_values = 1, 
                max_values = len(options) if max_value_type == "multiple" else 1,
                options = options,
                placeholder="Choose categories to add the role to"
            ))


class RolesView(View):
    def __init__(self, *, timeout: Optional[float] = None, role_category: str, max_value_type: Literal["single", "multiple"] = "multiple"):
        super().__init__(timeout=timeout)

        options = rp_conf.generate_role_options(role_category)

        self.add_item(Dropdown(
            min_values = 1,
            max_values = len(options) if max_value_type == "multiple" else 1,
            options = options,
            placeholder = "Choose the roles to remove"
        ))


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
