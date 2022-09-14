from typing import List, Literal, Optional
import discord
import stringcase
from discord.ext import commands
from discord import app_commands

from src.utils.config import RolePickerConfig
from src.utils.helper import dict_has_key
from src.utils.ui import Dropdown, Button, Modal, View


class RoleCategoryModal(Modal):
    def __init__(self, *, title: str, timeout: Optional[float] = None, custom_id: Optional[str] = None) -> None:
        super().__init__(title=title, timeout=timeout, custom_id=custom_id)

        self.add_item(discord.ui.TextInput(
            label='Name',
            placeholder='Enter category name',
            custom_id="label"
        ))
        
        self.add_item(discord.ui.TextInput(
            label='Description',
            placeholder='Enter description',
            style=discord.TextStyle.long,
            required=False,
            max_length=300,
            custom_id="description"
        ))


class RoleModal(Modal):
    def __init__(self, *, title: str, timeout: Optional[float] = None, custom_id: Optional[str] = None) -> None:
        super().__init__(title=title, timeout=timeout, custom_id=custom_id)

        self.add_item(discord.ui.TextInput(
            label='Role ID',
            placeholder='Enter role ID',
            custom_id='id'
        ))
    
        self.add_item(discord.ui.TextInput(
            label='Role Label',
            placeholder='Enter role label (if no label is provided, the role name is taken)',
            required=False,
            custom_id='label'
        ))

        self.add_item(discord.ui.TextInput(
            label='Role Description',
            placeholder='Enter role description',
            style=discord.TextStyle.long,
            required=False,
            max_length=100,
            custom_id='description'
        ))

        self.add_item(discord.ui.TextInput(
            label='Emoji ID',
            placeholder='Enter emoji ID',
            required=False,
            custom_id='emoji'
        ))


class RoleCategoryView(View):
    def __init__(self, *, timeout: Optional[float] = None, input_type: Literal["button", "select"] = "button", max_value_type: Literal["single", "multiple"] = "multiple", is_delete: bool = False):
        super().__init__(timeout=timeout)

        rp_conf = RolePickerConfig()

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
    def __init__(self, *, timeout: Optional[float] = None, role_category: str):
        super().__init__(timeout=timeout)

        rp_conf = RolePickerConfig()
        options = rp_conf.generate_role_options(role_category)

        self.add_item(Dropdown(
            min_values = 1,
            max_values = len(options),
            options = options,
            placeholder = "Choose the roles to remove"
        ))


class RolePicker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.command(pass_context=True)
    async def role_picker(self, ctx: commands.Context):
        """A message command that activates the role picker feature.

        User Flow
        ----------
            * Sends user an array of role categories to choose from
            * The user is presented a select menu with roles from the chosen role category
            * User can use the select menu to add or remove roles
        """

        rp_conf = RolePickerConfig()

        view = View()
        for category in rp_conf.role_categories:
            view.add_item(Button(label=category["label"], value=category["name"]))

        message = await ctx.send("Welcome to the bias picker, please select a role category", view=view)
        
        await view.wait()
        await message.delete()

        role_category = view.values

        roles = rp_conf.get_roles(role_category)
        role_ids = rp_conf.get_role_ids(role_category)
        user_role_ids = [role.id for role in ctx.author.roles]
        options: List[discord.SelectOption] = []

        for role in roles:
            option = discord.SelectOption(label=role["label"], value=rp_conf.get_role_id(role, role_category))

            if option.value in user_role_ids:
                option.default = True

            if dict_has_key(role, "emoji"):
                option.emoji = role["emoji"]

            options.append(option)

        view = View()
        view.add_item(Dropdown(
            min_values = 0, 
            max_values = len(options),
            options = options
        ))

        message = await ctx.send(f"Select roles!", view=view)

        await view.wait()
        await message.delete()
        
        selected_role_ids = [int(role_id) for role_id in view.values]
        common_current_role_ids = list(set(user_role_ids).intersection(set(role_ids)))
        common_selected_role_ids = list(set(selected_role_ids).intersection(set(user_role_ids)))

        role_ids_to_add = [role_id for role_id in selected_role_ids if role_id not in common_selected_role_ids]
        role_ids_to_del = [role_id for role_id in common_current_role_ids if role_id not in common_selected_role_ids]

        for role_id in role_ids_to_add:
            role = ctx.guild.get_role(int(role_id))
            await ctx.author.add_roles(role)

        for role_id in role_ids_to_del:
            role = ctx.guild.get_role(int(role_id))
            await ctx.author.remove_roles(role)


    @app_commands.command(name="add_role_category")
    @app_commands.default_permissions(manage_roles=True)
    async def add_role_category(self, interaction: discord.Interaction):
        """A slash command that allows users with appropriate permissions to add Role Categories.

        User Flow
        ----------
            * Sends user a modal of type `RoleCategoryModal`
            * Takes user input and creates a new role category in the `roles.yaml` file

        Permissions
        ----------
        `manage_roles`
        """

        modal = RoleCategoryModal(title="Role Category", custom_id="role_modal")

        await interaction.response.send_modal(modal)
        await modal.wait()

        rp_conf = RolePickerConfig()

        ori_data = rp_conf.get_data()
        copied_data = ori_data.copy()
        new_category = modal.get_values()
        new_key = stringcase.snakecase(str(new_category["label"]))
        new_category["name"] = new_key

        copied_data["categories"]["role_categories"].append(new_category)

        rp_conf.dump(copied_data)

    
    @app_commands.command(name="add_role")
    @app_commands.default_permissions(manage_roles=True)
    async def add_role(self, interaction: discord.Interaction):
        """A slash command that allows users with appropriate permissions to add Roles to Role Categories.

        User Flow
        ----------
            * Sends user a modal of type `RoleModal`
            * Takes user input and adds a new role to one or many role category(ies) in the `roles.yaml` file

        Permissions
        ----------
        `manage_roles`
        """

        modal = RoleModal(title="Add Role", custom_id="add_role")
        
        await interaction.response.send_modal(modal)
        await modal.wait()
        
        # TODO: Change to Select menu when Discord py Modals support Select menus
        rp_conf = RolePickerConfig()
        options = rp_conf.generate_role_category_options()

        view = View()
        view.add_item(Dropdown(
            min_values = 0, 
            max_values = len(options),
            options = options,
            placeholder="Choose categories to add the role to"
        ))

        message = await interaction.followup.send("Please select categories to add the role to", view=view)

        await view.wait()
        await message.delete()

        new_role = modal.get_values()

        if not dict_has_key(new_role, "label"):
            role = interaction.guild.get_role(int(new_role["id"]))
            new_role["label"] = role.name

        new_role["name"] = stringcase.snakecase(str(new_role["label"]))

        role_categories = view.values

        ori_data = rp_conf.get_data()
        copied_data = ori_data.copy()

        for role_category in role_categories:
            if role_category == "main" or role_category == "sub":
                new_role["ids"][role_category] = int(new_role["id"])
                new_role.pop("id", None)
                copied_data["members"]["roles"].append(new_role)
            else:
                new_role["id"] = int(new_role["id"])
                
                if not dict_has_key(copied_data, role_category):
                    copied_data[role_category] = {}
                    copied_data[role_category]["roles"] = []

                copied_data[role_category]["roles"].append(new_role)

        rp_conf.dump(copied_data)


    @app_commands.command(name="remove_role")
    @app_commands.default_permissions(manage_roles=True)
    async def remove_role(self, interaction: discord.Interaction):
        view = RoleCategoryView(input_type="button")

        await interaction.response.send_message("Select a role category to remove a role from", view=view)
        await view.wait()
        message = await interaction.original_response()
        await message.delete()

        role_category = view.values

        view = RolesView(role_category=role_category)

        message = await interaction.followup.send(f"Select role(s) to remove from {role_category} category", view=view)
        await view.wait()
        await message.delete()

        role_ids_to_remove = [int(role_id) for role_id in view.values]
        rp_conf = RolePickerConfig()
        roles = rp_conf.get_roles(role_category)

        ori_data = rp_conf.get_data()
        copied_data = ori_data.copy()

        if role_category == "main" or role_category == "sub":
            for role in roles:
                if role["ids"][role_category] in role_ids_to_remove:
                    del copied_data["member"]["roles"]["ids"][role_category]
        else:
            roles_to_keep = [role for role in roles if role["id"] not in role_ids_to_remove]
            copied_data[role_category]["roles"] = roles_to_keep

        rp_conf.dump(copied_data)


    @app_commands.command(name="delete_role_categories")
    @app_commands.default_permissions(manage_roles=True)
    async def delete_role_categories(self, interaction: discord.Interaction):
        view = RoleCategoryView(input_type="select", is_delete=True)

        await interaction.response.send_message("Select role category(ies) to delete", view=view)
        await view.wait()
        message = await interaction.original_response()
        await message.delete()

        # TODO: Add double confirmation view

        role_categories = view.values
        rp_conf = RolePickerConfig()
        ori_data = rp_conf.get_data()
        copied_data = ori_data.copy()

        for role_category in role_categories:
            copied_data["categories"]["role_categories"] = [rc for rc in rp_conf.role_categories if rc["name"] != role_category]
            del copied_data[role_category]


async def setup(bot):
    await bot.add_cog(RolePicker(bot))
