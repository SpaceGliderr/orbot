import re
from typing import Any, List, Optional, Tuple

import discord
from ruamel.yaml import YAML

from src.utils.helper import dict_has_key, get_from_dict

yaml = YAML(typ="safe")


class RolePickerConfig:
    """The RolePickerConfig class helps load the `roles.yaml` file and provides other util methods to manipulate the extracted data."""

    def __init__(self) -> None:
        with open("src/data/roles.yaml", "r") as roles_file:
            self._data = yaml.load(roles_file)

    @property
    def role_categories(self):
        """Get the role categories."""
        return get_from_dict(self._data, ["categories", "role_categories"])

    @property
    def data(self):
        """Get the extracted data."""
        return self._data

    def get_data(self):
        """Get a copied version of the extracted data."""
        return self._data.copy()

    def get_roles(self, category: str):
        """Get the list of roles in a role category."""
        return get_from_dict(self._data, [category, "roles"])

    def get_role_ids(self, category: str):
        """Get a list of role ids from the roles in a role category."""
        return [role["id"] for role in self.get_roles(category)]

    def get_role_category(self, category_name: str):
        """Get the entire role category. Returns a tuple with the structure (`index`, `category`)."""
        return next(
            ((idx, category) for idx, category in enumerate(self.role_categories) if category["name"] == category_name),
            None,
        )

    def get_role_by_id(self, role_category: str, role_id: int):
        """Get the entire role by role ID. Returns a tuple with the structure (`index`, `role`)."""
        return next(
            ((idx, role) for idx, role in enumerate(self.get_roles(role_category)) if role["id"] == role_id), None
        )

    def generate_option(self, dic: dict, value: Any, defaults: Optional[Any] = None):
        """Generates a list of select options."""
        option = discord.SelectOption(label=dic["label"], value=value)

        if defaults is not None and option.value in defaults:
            option.default = True

        if dict_has_key(dic, "emoji"):
            option.emoji = dic["emoji"]

        if dict_has_key(dic, "description"):
            option.description = dic["description"]

        return option

    def generate_role_options(self, role_category, defaults: Optional[Any] = None):
        """Generates a list of select options for roles."""
        return [self.generate_option(role, role["id"], defaults) for role in self.get_roles(role_category)]

    def generate_role_category_options(self, defaults: Optional[Any] = None):
        """Generates a list of select options for role categories."""
        return [self.generate_option(category, category["name"], defaults) for category in self.role_categories]

    def generate_all_embeds(self):
        """Generates a list of role category and role embeds."""
        embeds = []

        role_categories_embed = discord.Embed(
            title="Role Categories", description="Shows the role categories available in this server:\n\u200B"
        )
        role_categories_embed.set_footer(text=f"Page 1 of {len(self.role_categories) + 1}")

        for idx, role_category in enumerate(self.role_categories):
            postfix_text = ""
            if role_category != self.role_categories[-1]:
                postfix_text = "\n\u200B"

            role_categories_embed.add_field(
                name=role_category["label"],
                value=f"{role_category['description']}{postfix_text}"
                if dict_has_key(role_category, "description")
                else f"-No description-{postfix_text}",
                inline=False,
            )

            roles = self.get_roles(role_category["name"])

            embed = discord.Embed(
                title=role_category["label"],
                description=f"Shows all roles under the {role_category['label']} category\n\u200B",
            )

            for role in roles:
                value = f"Server Role: <@&{role['id']}>"

                if dict_has_key(role, "description"):
                    value += f"\nDescription: {role['description']}"

                if dict_has_key(role, "emoji"):
                    value += f"\nEmoji: {role['emoji']}"

                if role != roles[-1]:
                    value += "\n\u200B"

                embed.add_field(name=role["label"], value=value, inline=False)

            embed.set_footer(text=f"Page {idx + 2} of {len(self.role_categories) + 1}")
            embeds.append(embed)

        embeds.insert(0, role_categories_embed)

        return embeds

    def generate_role_picker_content(self):
        content = "Welcome to the LOONA Discord server's own Role Picker!\n\n__**Role Categories**__\n"

        embed = discord.Embed(title="**__Available Roles__**")

        role_categories = [
            role_category for role_category in self.role_categories if self.get_roles(role_category["name"]) is not None
        ]  # Filter out role categories that do not have roles

        for role_category in role_categories:
            content += f'`{role_category["label"]}`'

            if dict_has_key(role_category, "description"):
                content += f' ➡️ {role_category["description"]}'

            content += "\n"

            roles = self.get_roles(role_category["name"])

            value = ""
            for role in roles:
                value += f'`{role["label"]}`'

                if role != roles[-1]:
                    value += ", "

            if role_category != role_categories[-1]:
                value += "\n\u200B"

            embed.add_field(name=f"{role_category['label']} Roles", value=value, inline=False)

        content += "\n⚠️ For more information on specific roles, descriptions are provided in the select menus\n⚠️ Roles in the LOOΠΔ (Main) category are ordered from OT12 - subunits - individual member roles. The exact order is shown in the select menu. If you'd like your role to be a specific color, make sure all the roles before that aren't selected"

        return content, embed

    def dump(self, data):
        """Dump data into the `roles.yaml` file."""
        with open("src/data/roles.yaml", "w") as roles_file:
            yaml.dump(data, roles_file)


class CMAutoPostConfig:
    """The CMAutoPostConfig class helps load the `cm_auto_post.yaml` file and provides other util methods to manipulate the extracted data."""

    def __init__(self) -> None:
        with open("src/cm_auto_post.yaml", "r") as cm_auto_post_file:
            self._data = yaml.load(cm_auto_post_file)

    @property
    def post_channels(self):
        """Get the post channels."""
        return get_from_dict(self._data, ["config", "post_channels"])

    @property
    def data(self):
        """Get the extracted data."""
        return self._data

    @staticmethod
    def get_user_ids():
        # TODO: Move this to fansite.py
        with open("src/cogs/cm_auto_post/IDs.txt") as data:
            lines = data.read().splitlines()
            return [user_id for user_id in lines]

    @staticmethod
    def generate_post_caption(caption_credits: Optional[Tuple[str, str]], post_details: Optional[dict] = None):
        if post_details is not None and post_details != {}:
            if dict_has_key(post_details, "caption"):
                return f"```ml\n{post_details['caption']}\n```"

            caption = "```ml\n"

            if dict_has_key(post_details, "event_details"):
                caption += f'{post_details["event_details"]} '

            if caption_credits is not None:
                caption += f'| cr: {caption_credits[0]} (@{caption_credits[1]})'

            caption += "\n```"

            return caption
        return None


    @staticmethod
    def anatomize_post_caption(caption: str):
        name = re.search(r"cr:\s{1}.+?\(", caption)
        username = re.search(r"\(@.+?\)", caption)

        if name is not None and username is not None:
            # Split the name by removing `cr: ` and username by removing the `@()`
            return (name.group()[4:-2], username.group()[2:-1])
        
        return None


    def get_data(self):
        """Get a copied version of the extracted data."""
        return self._data.copy()

    def get_post_channel(self, channel_id: str):
        """Search for a post channel. Returns a tuple with the structure (`index`, `channel`)."""
        return next(
            ((idx, channel) for idx, channel in enumerate(self.post_channels) if channel["id"] == channel_id),
            None,
        )

    def generate_post_channel_options(self):
        """Generates a list of select options for post channels."""
        return [discord.SelectOption(label=post_channel["label"], value=post_channel["id"]) for post_channel in self.post_channels]

    def dump(self, data):
        """Dump data into the `cm_auto_post.yaml` file."""
        with open("src/cm_auto_post.yaml", "w") as cm_auto_post_file:
            yaml.dump(data, cm_auto_post_file)