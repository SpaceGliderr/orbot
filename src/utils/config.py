from typing import List
from ruamel.yaml import YAML
from src.utils.helper import get_from_dict


yaml = YAML(typ="safe")


class RolePickerConfig:
    def __init__(self) -> None:
        self.data = yaml.load(open("src/roles.yaml"))


    @property
    def role_categories(self):
        return get_from_dict(self.data, ["categories", "role_categories"])


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
