from typing import List
import discord
import stringcase
from discord.ext import commands
from discord import app_commands
from src.cogs.role_picker.ui import RoleCategoryModal, RoleCategoryView, RoleModal, RolesOverviewView, RolesView

from src.utils.config import RolePickerConfig
from src.utils.helper import dict_has_key
from src.utils.ui import Dropdown, Button, View


rp_conf = RolePickerConfig()


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
        options = rp_conf.generate_role_category_options()

        view = View()
        view.add_item(Dropdown(
            min_values = 1, 
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
        roles = rp_conf.get_roles(role_category)

        ori_data = rp_conf.get_data()
        copied_data = ori_data.copy()

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
        ori_data = rp_conf.get_data()
        copied_data = ori_data.copy()

        for role_category in role_categories:
            copied_data["categories"]["role_categories"] = [rc for rc in rp_conf.role_categories if rc["name"] != role_category]
            del copied_data[role_category]

        rp_conf.dump(copied_data)


    @app_commands.command(name="edit_role")
    @app_commands.default_permissions(manage_roles=True)
    async def edit_role(self, interaction: discord.Interaction):
        view = RoleCategoryView(input_type="button")

        await interaction.response.send_message("Select role category that the role is in", view=view)
        await view.wait()
        message = await interaction.original_response()
        await message.delete()

        role_category = view.values

        view = RolesView(role_category=role_category, max_value_type="single")

        await interaction.response.send_message("Select role to edit", view=view)
        await view.wait()
        message = await interaction.original_response()
        await message.delete()

        role_id = view.values[0]
        idx, role = rp_conf.get_role_by_id(role_category, role_id)
        
        modal = RoleModal(title="Edit Role", defaults=role)
        view.interaction.response.send_modal(modal)
        await modal.wait()

        edited_role = modal.get_values()
        ori_data = rp_conf.get_data()
        copied_data = ori_data.copy()

        edited_role["id"] = int(edited_role["id"])
        copied_data[role_category]["roles"][idx] = edited_role

        rp_conf.dump(copied_data)


    @app_commands.command(name="edit_role_category")
    @app_commands.default_permissions(manage_roles=True)
    async def edit_role_category(self, interaction: discord.Interaction):
        view = RoleCategoryView(input_type="button")

        await interaction.response.send_message("Select role category to edit", view=view)
        await view.wait()
        message = await interaction.original_response()
        await message.delete()

        role_category = view.values
        
        idx, category_details = rp_conf.get_role_category(role_category)

        modal = RoleCategoryModal(title="Edit Role", defaults=category_details)
        await view.interaction.response.send_modal(modal)
        await modal.wait()

        edited_category = modal.get_values()
        ori_data = rp_conf.get_data()
        copied_data = ori_data.copy()

        copied_data["categories"]["role_categories"][idx] = edited_category

        rp_conf.dump(copied_data)


    @app_commands.command(name="overview")
    async def roles_overview(self, interaction: discord.Interaction):
        embeds = rp_conf.generate_all_embeds()
        view = RolesOverviewView(embeds=embeds)

        await interaction.response.send_message(embed=embeds[0], view=view)


async def setup(bot):
    await bot.add_cog(RolePicker(bot))
