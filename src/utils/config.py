from typing import Any, List, Optional

import discord
from ruamel.yaml import YAML

from src.utils.helper import dict_has_key, get_from_dict

yaml = YAML(typ="safe")


class RolePickerConfig:
    """The RolePickerConfig class helps load the `roles.yaml` file and provides other util methods to manipulate the extracted data."""

    def __init__(self) -> None:
        with open("src/roles.yaml", "r") as roles_file:
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
        roles = self.get_roles(category)
        return [self.get_role_id(role, category) for role in roles]

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
        return [
            self.generate_option(role, self.get_role_id(role, role_category), defaults)
            for role in self.get_roles(role_category)
        ]

    def generate_role_category_options(self, defaults: Optional[Any] = None):
        """Generates a list of select options for role categories."""
        return [self.generate_option(category, category["name"], defaults) for category in self.role_categories]

    def generate_all_embeds(self):
        """Generates a list of role category and role embeds."""
        embeds = []

        role_categories_embed = discord.Embed(
            title="Role Categories", description="Shows the role categories available in this server:\n\u200B"
        )

        for role_category in self.role_categories:
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

            embeds.append(embed)

        embeds.insert(0, role_categories_embed)

        return embeds

    def dump(self, data):
        """Dump data into the `roles.yaml` file."""
        with open("src/roles.yaml", "w") as roles_file:
            yaml.dump(data, roles_file)
