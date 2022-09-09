from ruamel.yaml import YAML

yaml = YAML(typ="safe")


class Preset:
    def __init__(self, data):
        self.name = data.get("name")
        self.type = data.get("type")


class DropdownOption:
    def __init__(self, data):
        self.text = data.get("text")
        self.description = data.get("description")
        self.code_name = data.get("code-name")

        if self.code_name is None or self.text is None:
            raise KeyError("Needs to have role id code and text")


class RoleRemovalOption:
    def __init__(self, data):
        self.text = data.get("text")
        self.description = data.get("description")
        self.emoji = data.get("emoji")


class ButtonOpensDropdownPreset(Preset):
    def __init__(self, data):
        super().__init__(data)
        self.dropdown_options = []
        self.role_remover = RoleRemovalOption(data["remove-role-option"])

        for option in data["dropdown-options"]:
            self.dropdown_options.append(DropdownOption(option))


def create_preset(data):
    type = data["type"]

    if type == "button-opens-dropdown":
        return ButtonOpensDropdownPreset(data)


class MessageBuilder:
    __slots__ = ("content", "view")

    def __init__(self, data, config):
        self.content = data["text"]
        self.view = ViewBuilder(data["view"], config)

    def kwargs(self):
        return {"content": self.content, "view": self.view.build()}


class ViewBuilder:
    __slots__ = ("preset", "default_component", "default_type", "action_rows")

    def __init__(self, data, config):
        preset_name = data.get("preset")
        self.default_component = data.get("default-component")
        self.default_type = data.get("default-type")

        if preset_name is None:
            self.preset = None
        else:
            self.preset = config.get_preset(preset_name)

        self.action_rows = []

        if len(data["action-rows"]) < 1 or len(data["action-rows"]) > 5:
            raise ValueError("View has an invalid amount of action rows!")

        for action_row_info in data["action-rows"]:
            self.action_rows.append(ActionRow(action_row_info, self))


class ActionRow:
    __slots__ = ("view", "elements")

    def __init__(self, data, view):
        self.elements = []
        self.view = view

        if len(data) < 1 or len(data) > 5:
            raise ValueError("Action row has an invalid amount of components!")

        for component_info in data:
            self.elements.append(build_component(view, self, component_info))


class ButtonBuilder:
    __slots__ = ("text", "emoji", "role_id", "type", "view", "action_row")

    def __init__(self, data, action_row, view: ViewBuilder):
        self.text = data.get("text")
        self.emoji = data.get("emoji")
        self.role_id = data.get("role-id")
        self.type = data.get("type")

        self.action_row = action_row
        self.view = view


def build_component(view, action_row, data):
    if isinstance(view.preset, ButtonOpensDropdownPreset):
        return ButtonBuilder(data, action_row, view)


class Config:
    __slots__ = ("presets", "messages")

    def __init__(self, data):
        self.messages = []
        self.presets = []

        for preset_data in data["presets"]:
            self.presets.append(create_preset(preset_data))

        for message_data in data["messages"]:
            self.messages.append(MessageBuilder(message_data, self))

    @classmethod
    def from_file(cls, file_name):
        data = yaml.load(open(file_name))

        return cls(data)

    def get_preset(self, preset_name):
        for preset in self.presets:
            if preset.name == preset_name:
                return preset

        raise KeyError("Preset not found")
