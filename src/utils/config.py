from typing import Any, List, Optional
from ruamel.yaml import YAML
from src.utils.helper import dict_has_key, get_from_dict

import discord


yaml = YAML(typ="safe")


class RolePickerConfig:
    def __init__(self) -> None:
        with open("src/roles.yaml", "r") as roles_file:
            self.data = yaml.load(roles_file)


    @property
    def role_categories(self):
        return get_from_dict(self.data, ["categories", "role_categories"])


    def get_data(self):
        return self.data


    def get_value(self, path: List[str]):
        return get_from_dict(self.data, path)


    def get_roles(self, category: str):
        if category == "main" or category == "sub":
            return get_from_dict(self.data, ["members", "roles"])
        else:
            return get_from_dict(self.data, [category, "roles"])


    def get_role_id(self, role, category: str):
        if category == "main" or category == "sub":
            return role["ids"][category]
        else:
            return role["id"]

    
    def get_role_ids(self, category: str):
        roles = self.get_roles(category)
        return [self.get_role_id(role, category) for role in roles]


    def generate_option(self, dic: dict, value: Any, defaults: Optional[Any] = None):
        option = discord.SelectOption(
            label=dic["label"],
            value=value
        )

        if defaults is not None and option.value in defaults:
                option.default = True

        if dict_has_key(dic, "emoji"):
            option.emoji = dic["emoji"]

        if dict_has_key(dic, "description"):
            option.description = dic["description"]
         
        return option


    def generate_role_options(self, role_category, defaults: Optional[Any] = None):
        return [self.generate_option(role, self.get_role_id(role, role_category), defaults) for role in self.get_roles(role_category)]

    
    def generate_role_category_options(self, is_delete: bool = False, defaults: Optional[Any] = None):
        return [self.generate_option(category, category["name"], defaults) for category in self.role_categories if is_delete and (not category["name"] == "main" or not category["sub"])]

    
    def dump(self, data):
        with open("src/roles.yaml", "w") as roles_file:
            yaml.dump(data, roles_file)
