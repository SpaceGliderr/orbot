from typing import Optional

import discord

from src.modules.ui.common import Modal


class PostChannelModal(Modal):
    """Creates a modal popup window to add or edit a Post Channel by inheriting the `Modal` class.

    Has 2 text inputs for `id` and `label`.

    Additional Parameters
    ----------
        * defaults: Optional[:class:`dict`]
            - Fills the default values for each text input. Possible keys: `id`, `label`.
    """

    def __init__(self, defaults: Optional[dict] = None, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.add_item(
            discord.ui.TextInput(
                label="Channel ID",
                placeholder="Enter channel ID",
                custom_id="id",
                default=defaults.get("id", None) if defaults is not None else None,
            )
        )

        self.add_item(
            discord.ui.TextInput(
                label="Channel Label",
                placeholder="Enter channel label (defaults to channel name)",
                custom_id="label",
                default=defaults.get("label", None) if defaults is not None else None,
            )
        )
