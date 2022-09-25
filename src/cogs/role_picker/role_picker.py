from typing import Optional

import discord
import stringcase
from discord import app_commands
from discord.ext import commands

from src.cogs.role_picker.ui import (
    PersistentRolesView,
    RoleCategoryModal,
    RoleCategoryView,
    RoleModal,
    RolesOverviewView,
    RolesView,
)
from src.utils.config import RolePickerConfig
from src.utils.helper import dict_has_key



class RolePicker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="setup")
    @app_commands.default_permissions(manage_roles=True)
    async def setup(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await interaction.response.send_message(
            content=f"The role picker has been successfully setup in <#{channel.id}>!"
        )
        await channel.send(
            content="Welcome to the bias picker, please select a role category", view=PersistentRolesView()
        )

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
        rp_conf = RolePickerConfig()

        modal = RoleCategoryModal(title="Add Role Category", custom_id="add_role_category_modal", timeout=90)

        await interaction.response.send_modal(modal)
        await modal.wait()

        data = rp_conf.get_data()
        new_category = modal.get_values()
        new_key = stringcase.snakecase(str(new_category["label"]))
        new_category["name"] = new_key

        data["categories"]["role_categories"].append(new_category)

        rp_conf.dump(data)

    @app_commands.command(name="add_role")
    @app_commands.default_permissions(manage_roles=True)
    async def add_role(self, interaction: discord.Interaction, role: discord.Role, emoji: Optional[str]):
        """A slash command that allows users with appropriate permissions to add Roles to Role Categories.

        User Flow
        ----------
            * Sends user a modal of type `RoleModal`
            * Takes user input and adds a new role to one or many role category(ies) in the `roles.yaml` file

        Permissions
        ----------
        `manage_roles`
        """
        rp_conf = RolePickerConfig()

        role_category_view = RoleCategoryView(input_type="select", stop_view=True, timeout=90)

        await interaction.response.send_message(
            content="Please select the role categories to add the role to", view=role_category_view
        )
        await role_category_view.wait()
        await interaction.delete_original_response()

        defaults = {"id": role.id, "label": role.name}

        if emoji is not None:
            defaults["emoji"] = emoji

        role_modal = RoleModal(title="Add Role", custom_id="add_role_modal", timeout=90, defaults=defaults)

        await role_category_view.interaction.response.send_modal(role_modal)
        await role_modal.wait()

        role_categories = role_category_view.values
        new_role = role_modal.get_values()

        if not dict_has_key(new_role, "label"):
            new_role["label"] = role.name

        new_role["name"] = stringcase.snakecase(str(new_role["label"]))
        new_role["id"] = int(new_role["id"])

        data = rp_conf.get_data()

        for role_category in role_categories:
            if not dict_has_key(data, role_category):
                data[role_category] = {}
                data[role_category]["roles"] = []

            data[role_category]["roles"].append(new_role)

        rp_conf.dump(data)

    @app_commands.command(name="remove_role")
    @app_commands.default_permissions(manage_roles=True)
    async def remove_role(self, interaction: discord.Interaction):
        rp_conf = RolePickerConfig()

        role_category_view = RoleCategoryView(input_type="button", stop_view=True, timeout=90)

        await interaction.response.send_message("Select a role category to remove a role from", view=role_category_view)
        await role_category_view.wait()
        await interaction.delete_original_response()

        role_category = role_category_view.values

        roles_view = RolesView(role_category=role_category, timeout=90)

        await role_category_view.interaction.response.send_message(
            f"Select role(s) to remove from {role_category} category", view=roles_view
        )
        await roles_view.wait()
        await role_category_view.interaction.delete_original_response()

        if roles_view.is_confirmed:
            role_ids_to_remove = [int(role_id) for role_id in roles_view.values]
            roles = rp_conf.get_roles(role_category)

            data = rp_conf.get_data()

            roles_to_keep = [role for role in roles if role["id"] not in role_ids_to_remove]
            data[role_category]["roles"] = roles_to_keep

            rp_conf.dump(data)
        else:
            await roles_view.interaction.response.send_message(content="No roles were removed")

    @app_commands.command(name="delete_role_categories")
    @app_commands.default_permissions(manage_roles=True)
    async def delete_role_categories(self, interaction: discord.Interaction):
        rp_conf = RolePickerConfig()

        role_category_view = RoleCategoryView(input_type="select", stop_view=True, timeout=90)

        await interaction.response.send_message("Select role category(ies) to delete", view=role_category_view)
        await role_category_view.wait()
        await interaction.delete_original_response()

        # TODO: Add double confirmation view

        role_categories = role_category_view.values
        data = rp_conf.get_data()

        for role_category in role_categories:
            data["categories"]["role_categories"] = [
                rc for rc in rp_conf.role_categories if rc["name"] != role_category
            ]
            del data[role_category]

        rp_conf.dump(data)

    @app_commands.command(name="edit_role")
    @app_commands.default_permissions(manage_roles=True)
    async def edit_role(self, interaction: discord.Interaction):
        rp_conf = RolePickerConfig()

        role_category_view = RoleCategoryView(input_type="button", stop_view=True, timeout=90)

        await interaction.response.send_message("Select role category that the role is in", view=role_category_view)
        await role_category_view.wait()
        await interaction.delete_original_response()

        role_category = role_category_view.values

        roles_view = RolesView(role_category=role_category, max_value_type="single", timeout=90)

        await role_category_view.interaction.response.send_message("Select role to edit", view=roles_view)
        await roles_view.wait()
        await role_category_view.interaction.delete_original_response()

        if roles_view.is_confirmed:
            role_id = int(roles_view.values[0])
            idx, role = rp_conf.get_role_by_id(role_category, role_id)

            role_modal = RoleModal(title="Edit Role", defaults=role, custom_id="edit_role")
            await roles_view.interaction.response.send_modal(role_modal)
            await role_modal.wait()

            edited_role = role_modal.get_values()
            data = rp_conf.get_data()

            edited_role["id"] = int(edited_role["id"])
            data[role_category]["roles"][idx] = {**data[role_category]["roles"][idx], **edited_role}

            rp_conf.dump(data)
        else:
            await roles_view.interaction.response.send_message(content="No roles were edited")

    @app_commands.command(name="edit_role_category")
    @app_commands.default_permissions(manage_roles=True)
    async def edit_role_category(self, interaction: discord.Interaction):
        rp_conf = RolePickerConfig()

        role_category_view = RoleCategoryView(input_type="button")

        await interaction.response.send_message("Select role category to edit", view=role_category_view, timeout=90)
        await role_category_view.wait()
        await interaction.delete_original_response()

        role_category = role_category_view.values

        idx, category_details = rp_conf.get_role_category(role_category)

        role_category_modal = RoleCategoryModal(
            title="Edit Role Category", defaults=category_details, custom_id="edit_role_category", timeout=90
        )
        await role_category_view.interaction.response.send_modal(role_category_modal)
        await role_category_modal.wait()

        edited_category = role_category_modal.get_values()
        data = rp_conf.get_data()

        data["categories"]["role_categories"][idx] = {
            **data["categories"]["role_categories"][idx],
            **edited_category,
        }

        rp_conf.dump(data)

    @app_commands.command(name="overview")
    async def roles_overview(self, interaction: discord.Interaction):
        rp_conf = RolePickerConfig()

        embeds = rp_conf.generate_all_embeds()
        view = RolesOverviewView(embeds=embeds)

        await interaction.response.send_message(embed=embeds[0], view=view)


async def setup(bot):
    await bot.add_cog(RolePicker(bot))
