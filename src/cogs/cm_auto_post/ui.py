from importlib.metadata import files
from typing import Any, List, Optional, Union
from src.utils.ui import Button, Modal, View

import discord

from src.utils.helper import dict_has_key
from src.utils.config import CMAutoPostConfig


class PostChannelModal(Modal):
    def __init__(
        self,
        *,
        title: str,
        timeout: Optional[float] = None,
        custom_id: Optional[str] = None,
        success_msg: Optional[str] = None,
        error_msg: Optional[str] = None,
        defaults: Optional[dict] = None,
        checks: Optional[List[dict]] = None,
    ) -> None:
        super().__init__(
            title=title,
            timeout=timeout,
            custom_id=custom_id,
            success_msg=success_msg,
            error_msg=error_msg,
            checks=checks,
        )

        self.add_item(
            discord.ui.TextInput(
                label="Channel ID",
                placeholder="Enter channel ID",
                custom_id="id",
                default=defaults["id"] if defaults is not None else None,
            )
        )

        self.add_item(
            discord.ui.TextInput(
                label="Channel Label",
                placeholder="Enter channel label (defaults to channel name)",
                custom_id="label",
                default=defaults["label"] if defaults is not None else None,
            )
        )


class PostChannelView(View):
    def __init__(
        self,
        *,
        timeout: Optional[float] = None,
        stop_view: bool = False,
    ):
        super().__init__(timeout=timeout)

        cmap_conf = CMAutoPostConfig()

        for channel in cmap_conf.post_channels:
            self.add_item(
                Button(
                    label=channel["label"], value=channel["id"], custom_id=channel["name"], stop_view=stop_view
                )
            )


