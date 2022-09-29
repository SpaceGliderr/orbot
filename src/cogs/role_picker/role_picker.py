from typing import Optional, Union

import discord
import stringcase
from discord import Permissions, app_commands
from discord.ext import commands

from src.cogs.role_picker.ui import (
    PersistentRolePickerView,
    RoleCategoryModal,
    RoleCategoryView,
    RoleModal,
    RolesOverviewView,
    RolesView,
)
from src.utils.config import RolePickerConfig
from src.utils.helper import dict_has_key, get_from_dict


class RolePicker(commands.GroupCog, name="role-picker"):
    def __init__(self, bot):
        self.bot = bot

    # =================================================================================================================
    # COMMAND GROUPS
    # =================================================================================================================
    add_group = app_commands.Group(
        name="add",
        description="Add new elements to the role picker.",
        default_permissions=Permissions(manage_roles=True),
        guild_only=True,
    )
    edit_group = app_commands.Group(
        name="edit",
        description="Edit existing elements in the role picker.",
        default_permissions=Permissions(manage_roles=True),
        guild_only=True,
    )
    delete_group = app_commands.Group(
        name="delete",
        description="Delete existing elements in the role picker",
        default_permissions=Permissions(manage_roles=True),
        guild_only=True,
    )

    # =================================================================================================================
    # FUNCTIONS
    # =================================================================================================================
    async def setup_or_refresh(self, scope: Union[discord.Guild, discord.TextChannel]):
        """A method to either setup or refresh the Role Picker message and view.

        Parameters
        ----------
            * scope: Union[:class:`discord.Guild`, :class:`discord.TextChannel`]
                - If a `Guild` instance is provided, the Role Picker will be updated in the original text channel it was setup in.
                - If a `TextChannel` instance is provided and it is the same text channel it was setup in, the Role Picker will update in that respective channel.
                - If a different `TextChannel` is provided compared to the one in the setup, the message in the old channel is deleted and replaced with a new message in the new specified channel.
        """
        rp_conf = RolePickerConfig()
        content, embed = rp_conf.generate_role_picker_content()

        send_new_msg_flag = True  # A flag that signifies whether a new message should be sent to the channel + whether the `roles.yaml` setup object must be updated

        setup = get_from_dict(rp_conf.data, ["role_picker", "setup"])
        if setup is not None:
            channel_id = setup["channel_id"]
            message_id = setup["message_id"]

            if isinstance(scope, discord.TextChannel) and scope.id != channel_id:
                # When the scope is a TextChannel instance and the role picker is being setup in a new channel,
                #   delete the old message in the old channel.
                # The `send_new_msg_flag` will be True, signifying that a new message must be sent and the setup in `roles.yaml` must be updated
                old_channel = await scope.guild.fetch_channel(channel_id)
                old_message = await old_channel.fetch_message(message_id)
                await old_message.delete()
            else:
                # Regardless of the scope instance, if the role picker is being updated in the same channel,
                #   the message in the respective channel is edited with the new content.
                # The `send_new_msg_flag` is set to False, no need to send a new message
                channel = await scope.fetch_channel(channel_id) if isinstance(scope, discord.Guild) else scope
                message = await channel.fetch_message(message_id)
                await message.edit(content=content, embed=embed, view=PersistentRolePickerView())
                send_new_msg_flag = False

        if send_new_msg_flag and isinstance(scope, discord.TextChannel):
            # The scope needs to be of a TextChannel instance as the bot needs to send a new message into that channel
            message = await scope.send(content=content, embed=embed, view=PersistentRolePickerView())

            # Updating the setup object in `roles.yaml`
            data = rp_conf.get_data()
            data["role_picker"] = {}
            data["role_picker"]["setup"] = {"message_id": message.id, "channel_id": scope.id}

            rp_conf.dump(data)

    # =================================================================================================================
    # GENERAL SLASH COMMANDS
    # =================================================================================================================
    @app_commands.command(name="overview", description="Shows all categories and roles.")
    @app_commands.guild_only()
    @app_commands.default_permissions(use_application_commands=True)
    async def overview(self, interaction: discord.Interaction):
        """A slash command that displays an overview of all Role Categories and Roles.

        User Flow
        ----------
            * Generates an array of embeds for Role Categories and Roles per category
            * Sends user a paginated `RolesOverviewView` with embeds

        Permissions
        ----------
        `use_application_commands`
        """
        rp_conf = RolePickerConfig()

        embeds = rp_conf.generate_all_embeds()
        view = RolesOverviewView(embeds=embeds)

        await interaction.response.send_message(embed=embeds[0], view=view)

    @app_commands.command(name="setup", description="Setup the role picker in a text channel.")
    @app_commands.guild_only()
    @app_commands.describe(channel="the text channel to setup in")
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.checks.has_permissions(manage_roles=True)
    async def setup(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """A slash command that sets up a persistent Role Picker in a user-specified text channel.

        Parameters
        ----------
            * channel: :class:`discord.TextChannel`
                - The text channel that the Role Picker will be set up in

        User Flow
        ----------
            * Receives `channel` as the user input
            * Sets up a `PersistentRolePickerView` in the `channel`

        Permissions
        ----------
        `manage_roles`
        """
        await interaction.response.send_message(
            content=f"The role picker has been successfully setup in <#{channel.id}>!", ephemeral=True
        )
        await self.setup_or_refresh(channel)

    @app_commands.command(
        name="refresh",
        description="Refresh the role picker in the setup text channel. Must run the `setup` command beforehand.",
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.checks.has_permissions(manage_roles=True)
    async def refresh(self, interaction: discord.Interaction):
        """A slash command that refreshes the persistent Role Picker in the text channel specified during the setup.

        Permissions
        ----------
        `manage_roles`
        """
        await self.setup_or_refresh(interaction.guild)

    # =================================================================================================================
    # ADD OPERATION SLASH COMMANDS
    # =================================================================================================================
    @add_group.command(name="category", description="Add a role category.")
    @app_commands.checks.has_permissions(manage_roles=True)
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

        # Send RoleCategoryModal
        modal = RoleCategoryModal(
            title="Add Role Category",
            custom_id="add_role_category_modal",
            timeout=90,
            success_msg="A new role category was successfully added!",
            error_msg="A few problems were encountered when adding a new role category, please try again!",
            checks=[{"custom_id": "limit", "regex": "(single|multiple)"}],
        )

        await interaction.response.send_modal(modal)
        timeout = await modal.wait()

        if timeout:
            await interaction.followup.send(content="The command has timed out, please try again!", ephemeral=True)
            return

        # Process and dump data
        data = rp_conf.get_data()
        new_category = modal.get_values()
        new_category["name"] = stringcase.snakecase(
            str(new_category["label"])
        )  # Generates a snakecased `name` attribute from the label
        new_category["limit"] = new_category["limit"].lower()

        data["categories"]["role_categories"].append(new_category)

        rp_conf.dump(data)

        # Update Role Picker message
        await self.setup_or_refresh(modal.interaction.guild)

    @add_group.command(name="role", description="Add a role to role category(ies).")
    @app_commands.describe(role="the server role to add", emoji="the role emoji")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def add_role(self, interaction: discord.Interaction, role: discord.Role, emoji: Optional[str]):
        """A slash command that allows users with appropriate permissions to add Roles to Role Categories.

        Parameters
        ----------
            * role: :class:`discord.Role`
                - The role to be added
            * emoji: Optional[:class:`str`]
                - The emoji associated to the role

        User Flow
        ----------
            * Sends user a modal of type `RoleModal`
            * Takes user input and adds a new role to one or many role category(ies) in the `roles.yaml` file

        Permissions
        ----------
        `manage_roles`
        """
        rp_conf = RolePickerConfig()

        # Send RoleCategoryView
        role_category_view = RoleCategoryView(input_type="select", stop_view=True, timeout=90)

        await interaction.response.send_message(
            content="Please select the role categories to add the role to", view=role_category_view
        )
        timeout = await role_category_view.wait()
        await interaction.delete_original_response()

        if timeout:
            await interaction.followup.send(content="The command has timed out, please try again!", ephemeral=True)
            return

        # Generates the defaults based on the user entered role and emoji
        defaults = {"id": role.id, "label": role.name}
        if emoji is not None:
            defaults["emoji"] = emoji

        # Send RoleModal
        role_modal = RoleModal(
            title="Add Role",
            custom_id="add_role_modal",
            timeout=90,
            defaults=defaults,
            success_msg="A new role was successfully added!",
            error_msg="A few problems were encountered when adding a new role, please try again!",
        )

        await role_category_view.interaction.response.send_modal(role_modal)
        timeout = await role_modal.wait()

        if timeout:
            await role_category_view.interaction.followup.send(
                content="The command has timed out, please try again!", ephemeral=True
            )
            return

        # Process data
        role_categories = role_category_view.values
        new_role = role_modal.get_values()

        if not dict_has_key(new_role, "label"):
            new_role["label"] = role.name

        new_role["name"] = stringcase.snakecase(
            str(new_role["label"])
        )  # Generates a snakecased `name` attribute from the label
        new_role["id"] = int(new_role["id"])

        # Dump data
        data = rp_conf.get_data()

        for role_category in role_categories:
            if not dict_has_key(data, role_category):
                data[role_category] = {}
                data[role_category]["roles"] = []

            data[role_category]["roles"].append(new_role)

        rp_conf.dump(data)

        # Update Role Picker message
        await self.setup_or_refresh(role_modal.interaction.guild)

    # =================================================================================================================
    # EDIT OPERATION SLASH COMMANDS
    # =================================================================================================================
    @edit_group.command(name="category", description="Edit an existing role category.")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def edit_role_category(self, interaction: discord.Interaction):
        """A slash command that allows users to edit an existing Role Category.

        User Flow
        ----------
            * Sends a `RoleCategoryView` to the user
            * Sends user a modal of type `RoleCategoryModal`
            * Takes user input and updates the role category in the `roles.yaml` file

        Permissions
        ----------
        `manage_roles`
        """
        rp_conf = RolePickerConfig()

        # Send RoleCategoryView
        role_category_view = RoleCategoryView(input_type="button", timeout=90, stop_view=True)

        await interaction.response.send_message("Select role category to edit", view=role_category_view)
        timeout = await role_category_view.wait()
        await interaction.delete_original_response()

        if timeout:
            await interaction.followup.send(content="The command has timed out, please try again!", ephemeral=True)
            return

        role_category = role_category_view.values

        idx, category_details = rp_conf.get_role_category(role_category)

        # Send RoleCategoryModal
        role_category_modal = RoleCategoryModal(
            title="Edit Role Category",
            defaults=category_details,
            custom_id="edit_role_category",
            timeout=90,
            success_msg="The role category was successfully edited!",
            error_msg="A few problems were encountered when editing the role category, please try again!",
            checks=[{"custom_id": "limit", "regex": "(single|multiple)"}],
        )

        await role_category_view.interaction.response.send_modal(role_category_modal)
        timeout = await role_category_modal.wait()

        if timeout:
            await role_category_view.interaction.followup.send(
                content="The command has timed out, please try again!", ephemeral=True
            )
            return

        # Process and dump data
        edited_category = role_category_modal.get_values()
        edited_category["name"] = stringcase.snakecase(
            str(edited_category["label"])
        )  # Generates a snakecased `name` attribute from the label
        edited_category["limit"] = edited_category["limit"].lower()

        data = rp_conf.get_data()
        data["categories"]["role_categories"][idx] = {
            **data["categories"]["role_categories"][idx],
            **edited_category,
        }

        data[edited_category["name"]] = data.pop(role_category)  # Replace the old key with the new key

        rp_conf.dump(data)

        # Update Role Picker message
        await self.setup_or_refresh(role_category_modal.interaction.guild)

    @edit_group.command(name="role", description="Edit an existing role.")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def edit_role(self, interaction: discord.Interaction):
        """A slash command that allows users to edit an existing Role in any Role Category.

        User Flow
        ----------
            * Sends a `RoleCategoryView` to the user
            * Sends a `RolesView` to the user
            * Sends a `RoleModal` to the user based on the selected Role
            * Takes user input and updates the role in the `roles.yaml` file

        Permissions
        ----------
        `manage_roles`
        """
        rp_conf = RolePickerConfig()

        # Send RoleCategoryView
        role_category_view = RoleCategoryView(input_type="button", stop_view=True, timeout=90)

        await interaction.response.send_message("Select role category that the role is in", view=role_category_view)
        timeout = await role_category_view.wait()
        await interaction.delete_original_response()

        if timeout:
            await interaction.followup.send(content="The command has timed out, please try again!", ephemeral=True)
            return

        role_category = role_category_view.values

        # Send RolesView
        roles_view = RolesView(role_category=role_category, max_value_type="single", timeout=90)

        await role_category_view.interaction.response.send_message("Select role to edit", view=roles_view)
        timeout = await roles_view.wait()
        await role_category_view.interaction.delete_original_response()

        if timeout:
            await role_category_view.interaction.followup.send(
                content="The command has timed out, please try again!", ephemeral=True
            )
            return

        if roles_view.is_confirmed:
            role_id = int(roles_view.values[0])
            idx, role = rp_conf.get_role_by_id(role_category, role_id)

            # Send RoleModal
            role_modal = RoleModal(
                title="Edit Role",
                defaults=role,
                custom_id="edit_role",
                success_msg="The role was successfully edited!",
                error_msg="A few problems were encountered when editing the role, please try again!",
            )
            await roles_view.interaction.response.send_modal(role_modal)
            await role_modal.wait()

            # Process and dump data
            edited_role = role_modal.get_values()
            edited_role["id"] = int(edited_role["id"])
            edited_role["name"] = stringcase.snakecase(
                str(edited_role["label"])
            )  # Generates a snakecased `name` attribute from the label

            data = rp_conf.get_data()
            data[role_category]["roles"][idx] = {**data[role_category]["roles"][idx], **edited_role}

            rp_conf.dump(data)

            # Update Role Picker message
            await self.setup_or_refresh(role_modal.interaction.guild)
        else:
            await roles_view.interaction.response.send_message(content="No roles were edited")

    # =================================================================================================================
    # DELETE OPERATION SLASH COMMANDS
    # =================================================================================================================
    @delete_group.command(name="categories", description="Delete role category(ies).")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def delete_role_categories(self, interaction: discord.Interaction):
        """A slash command that allows users to delete Role Category(ies).

        User Flow
        ----------
            * Sends a `RoleCategoryView` to the user
            * Removes selected role category(ies) in the `roles.yaml` file

        Permissions
        ----------
        `manage_roles`
        """
        rp_conf = RolePickerConfig()

        # Send RoleCategoryView
        role_category_view = RoleCategoryView(input_type="select", stop_view=True, timeout=90)

        await interaction.response.send_message("Select role category(ies) to delete", view=role_category_view)
        timeout = await role_category_view.wait()
        await interaction.delete_original_response()

        if timeout:
            await interaction.followup.send(content="The command has timed out, please try again!", ephemeral=True)
            return

        # TODO: Add double confirmation view

        # Process and dump data
        role_categories = role_category_view.values
        data = rp_conf.get_data()

        for role_category in role_categories:
            data["categories"]["role_categories"] = [
                rc for rc in rp_conf.role_categories if rc["name"] != role_category
            ]  # Delete element from the `role_categories` list
            if dict_has_key(data, role_category):
                del data[role_category]  # Delete key | attribute from the `roles.yaml` file itself

        rp_conf.dump(data)

        # Update Role Picker message
        await self.setup_or_refresh(role_category_view.interaction.guild)

    @delete_group.command(name="role", description="Remove a role from a role category.")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def remove_role(self, interaction: discord.Interaction):
        """A slash command that allows users to remove a Role from an existing Role Category.

        User Flow
        ----------
            * Sends a `RoleCategoryView` to the user
            * Sends a `RolesView` to the user
            * Removes selected roles from the role category in the `roles.yaml` file

        Permissions
        ----------
        `manage_roles`
        """
        rp_conf = RolePickerConfig()

        # Send RoleCategoryView
        role_category_view = RoleCategoryView(input_type="button", stop_view=True, timeout=90)

        await interaction.response.send_message("Select a role category to remove a role from", view=role_category_view)
        timeout = await role_category_view.wait()
        await interaction.delete_original_response()

        if timeout:
            await interaction.followup.send(content="The command has timed out, please try again!", ephemeral=True)
            return

        role_category = role_category_view.values

        # Send RolesView
        roles_view = RolesView(role_category=role_category, timeout=90)

        await role_category_view.interaction.response.send_message(
            f"Select role(s) to remove from {role_category} category", view=roles_view
        )
        timeout = await roles_view.wait()
        await role_category_view.interaction.delete_original_response()

        if timeout:
            await role_category_view.interaction.followup.send(
                content="The command has timed out, please try again!", ephemeral=True
            )
            return

        if roles_view.is_confirmed:
            # Process and dump data
            role_ids_to_remove = [
                int(role_id) for role_id in roles_view.values
            ]  # Make sure to convert it to `int` data type because views return `str`
            roles = rp_conf.get_roles(role_category)

            data = rp_conf.get_data()

            roles_to_keep = [
                role for role in roles if role["id"] not in role_ids_to_remove
            ]  # Keep role object if role ID is not to be removed
            if len(roles_to_keep) == 0:
                del data[role_category]
            else:
                data[role_category]["roles"] = roles_to_keep

            rp_conf.dump(data)

            # Update Role Picker message
            await self.setup_or_refresh(roles_view.interaction.guild)
        else:
            await roles_view.interaction.response.send_message(content="No roles were removed")


async def setup(bot):
    await bot.add_cog(RolePicker(bot))
