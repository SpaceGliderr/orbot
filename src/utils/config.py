import re
from typing import Any, List, Literal, Optional, Tuple

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
        """Generates a role picker content for the embed."""
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


class ContentPosterConfig:
    """The ContentPosterConfig class helps load the `content_poster.yaml` file and provides other util methods to manipulate the extracted data."""

    def __init__(self) -> None:
        with open("src/data/content_poster.yaml", "r") as content_poster_file:
            self._data = yaml.load(content_poster_file)

    @property
    def post_channels(self):
        """Get the post channels."""
        return get_from_dict(self._data, ["config", "post_channels"])

    @property
    def hashtag_filters(self):
        """Get hashtag filters."""
        return get_from_dict(self._data, ["config", "hashtag_filters"])

    @property
    def data(self):
        """Get the extracted data."""
        return self._data

    @property
    def active_posts(self):
        """Get the active posts object."""
        return get_from_dict(self._data, ["active_posts"])

    @staticmethod
    def generate_post_caption(
        caption_credits: Optional[Tuple[str, str]] = None, post_caption_details: Optional[dict] = None
    ):
        """Generates the post caption."""
        if (
            post_caption_details is not None
            and post_caption_details != {}
            and dict_has_key(post_caption_details, "caption")
        ):
            caption = f'```ml\n{post_caption_details["caption"].replace("```", "")} '

            if caption_credits is not None and post_caption_details["has_credits"]:
                caption += f"| cr: {caption_credits[0]} (@{caption_credits[1]})"

            caption += "\n```"

            return caption
        return None

    @staticmethod
    def anatomize_post_caption(caption: str):
        """Breaks down the post caption and extracts the caption credits."""
        name = re.search(r"cr:\s{1}.+?\(", caption)
        username = re.search(r"\(@.+?\)", caption)

        if name is not None and username is not None:
            # Split the name by removing `cr: ` and username by removing the `@()`
            return (name.group()[4:-2], username.group()[2:-1])

        return None

    @staticmethod
    def get_post_caption_content(caption: str):
        """Breaks down the post caption and extracts the contents."""
        content = re.search(r".+\s{1}\|", caption)
        has_credits = True

        if content is None:
            # Return a custom caption
            content = re.search(r"\n.+", caption).group().strip()
            has_credits = False
        else:
            content = content.group()[:-2]

        return {"caption": content, "has_credits": has_credits}

    def get_feed_channel(self, client: discord.Client):
        """Gets the feed channel instance."""
        try:
            return client.get_channel(self.data["config"]["feed_channel_id"])
        except:
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

    def generate_post_channel_options(self, defaults: Optional[List[str]] = None):
        """Generates a list of select options for post channels."""
        return [
            discord.SelectOption(
                label=post_channel["label"],
                value=post_channel["id"],
                default=str(post_channel["id"]) in defaults if defaults is not None else None,
            )
            for post_channel in self.post_channels
        ]

    def add_active_post(self, message_id: int, tweet_details: dict):
        """Adds active post to the config file."""
        data = self.get_data()
        data["active_posts"][str(message_id)] = tweet_details
        self.dump(data)

    def remove_active_post(self, message_id: int):
        """Removes active post from the config file."""
        data = self.get_data()
        del data["active_posts"][str(message_id)]
        self.dump(data)

    def dump(self, data):
        """Dump data into the `content_poster.yaml` file."""
        with open("src/data/content_poster.yaml", "w") as content_poster_file:
            yaml.dump(data, content_poster_file)


class GoogleCloudConfig:
    """The GoogleCloudConfig class helps load the `google_cloud.yaml` file and provides other util methods to manipulate the extracted data."""

    def __init__(self) -> None:
        with open("src/data/google_cloud.yaml", "r") as google_cloud_file:
            self._data = yaml.load(google_cloud_file)

    @property
    def active_form_watches(self) -> dict | None:
        """Get the list of active form watches."""
        return get_from_dict(self._data, ["active_form_watches"])

    @property
    def active_form_schemas(self) -> dict | None:
        """Get the list of active form schemas."""
        return get_from_dict(self._data, ["active_form_schemas"])

    @property
    def form_channel_id(self):
        """Get the default broadcast channel ID."""
        return get_from_dict(self._data, ["form_channel_id"])

    @property
    def topics(self):
        """Get the list of Google Topic subscription paths."""
        return get_from_dict(self._data, ["topics"])

    def get_question_details(self, question_id: str, form_id: str):
        """Get the question title based on the question ID and form ID."""
        form_schema = get_from_dict(self.active_form_schemas, [form_id])
        if form_schema:
            return get_from_dict(form_schema["questions"], [question_id])
        return None

    def search_active_form_watch(
        self,
        form_id: str,
        watch_id: Optional[str] = None,
        event_type: Optional[str] = None,
        topic_name: Optional[str] = None,
    ):
        """Search the `google_cloud.yaml` file for an active form watch."""
        result = get_from_dict(self.active_form_watches, [form_id])

        def is_valid(watch: dict):
            if watch["form_id"] != form_id:
                return False
            if watch_id and not watch["watch_id"] == watch_id:
                return False
            if event_type and not watch["event_type"] == event_type:
                return False
            if topic_name and not watch["topic_name"] == topic_name:
                return False
            # TODO: Double check the expiry date with the current date
            return True

        if result:
            result = next(
                ((idx, watch) for idx, watch in enumerate(result) if is_valid(watch)),
                None,
            )
        return result

    def search_active_form_watches(self, form_id: str):
        """Search the `google_cloud.yaml` file for all form watches under a specific form ID."""
        return get_from_dict(self.active_form_watches, [form_id])

    def insert_new_form_watch(self, result: dict, form_id: str, channel_id: str):
        """Insert a new form watch object into the `google_cloud.yaml` file."""
        data = self.get_data()
        new_form = {
            "form_id": form_id,
            "watch_id": result["id"],
            "event_type": result["eventType"],
            "topic_name": get_from_dict(result, ["target", "topic", "topicName"]),
            "expire_time": result["expireTime"],
            "broadcast_channel_id": channel_id,
        }

        if self.search_active_form_watches(form_id=form_id):
            data["active_form_watches"][form_id].append(new_form)
        else:
            data["active_form_watches"][form_id] = [new_form]

        self.dump(data)

    def update_form_watch(self, form_id: str, channel_id: str, event_type: Optional[str] = None):
        """Update a form watch object in the `google_cloud.yaml` file."""
        idx, watch = self.search_active_form_watch(form_id=form_id, event_type=event_type)

        data = self.get_data()
        data["active_form_watches"][form_id][idx] = {**watch, "broadcast_channel_id": channel_id}

        self.dump(data)

    def delete_form_watch(
        self,
        form_id: str,
        watch_id: Optional[str] = None,
        event_type: Optional[str] = None,
        topic_name: Optional[str] = None,
    ):
        """Delete a form watch object in the `google_cloud.yaml` file based on form ID, watch ID, event type and topic name."""
        result = self.search_active_form_watch(
            form_id=form_id, watch_id=watch_id, event_type=event_type, topic_name=topic_name
        )

        if result:
            data = self.get_data()
            del data["active_form_watches"][form_id][result[0]]

        self.dump(data=data)
        return result == None

    def delete_form_watches_with_index(self, form_watches: List[Tuple[int, dict]]):
        """Delete a form watch object in the `google_cloud.yaml` file based on the index under a specific form ID."""
        data = self.get_data()

        for idx, watch in form_watches:
            del data["active_form_watches"][watch["form_id"]][idx]

            if len(data["active_form_watches"][watch["form_id"]]) == 0:
                del data["active_form_watches"][watch["form_id"]]

        self.dump(data=data)

    def upsert_form_schema(self, form_id: str, schema: dict):
        """Insert or update a form schema object in the `google_cloud.yaml` file."""
        data = self.get_data()
        data["active_form_schemas"][form_id] = schema
        self.dump(data)

    def delete_form_schema(self, form_id: str):
        """Delete a form schema object in the `google_cloud.yaml` file."""
        if get_from_dict(self.active_form_schemas, [form_id]):
            data = self.get_data()
            del data[form_id]
            self.dump(data)
            return True
        return False

    def subscribe_topic(self, topic_name: str):
        """Subscribe to a Google topic path in the `google_cloud.yaml` file."""
        if topic_name not in self.topics:
            data = self.get_data()
            data["topics"].append(topic_name)
            self.dump(data)
            return True
        return False

    def unsubscribe_topic(self, topic_name: str):
        """Unsubscribe from a Google topic path in the `google_cloud.yaml` file."""
        if topic_name in self.topics:
            data = self.get_data()
            data["topics"].remove(topic_name)
            self.dump(data)
            return True
        return False

    def manage_channel(self, action: Literal["upsert", "delete"], channel: Optional[discord.TextChannel]):
        """Insert, update or delete the default broadcast channel."""
        data = self.get_data()
        data["form_channel_id"] = None if action == "delete" else channel.id if channel else self.form_channel_id
        self.dump(data)

    def dump(self, data):
        """Dump data into the `google_cloud.yaml` file."""
        with open("src/data/google_cloud.yaml", "w") as google_cloud_file:
            yaml.dump(data, google_cloud_file)


class ThreadEventsConfig:
    """The ThreadEventsConfig class helps load the `thread_events.yaml` file and provides other util methods to manipulate the extracted data."""

    def __init__(self) -> None:
        with open("src/data/thread_events.yaml", "r") as forum_events_file:
            self._data = yaml.load(forum_events_file)

    @property
    def events(self):
        """Get the list of thread events."""
        return get_from_dict(self._data, ["events"])

    def get_data(self):
        """Get a copied version of the extracted data."""
        return self._data.copy()

    def get_thread_event(self, event: Literal["on_thread_create", "on_thread_update"], channel_id: int):
        """Get a specific thread event based on the provided event and channel ID."""
        event = get_from_dict(self._data, ["events", event])
        channel = get_from_dict(event, [channel_id])
        return channel if channel else None

    def upsert_thread_event(
        self,
        event: Literal["on_thread_create", "on_thread_update"],
        channel_id: int,
        ordered: bool,
        react_emojis: List[int | str],
        replace_reactions: bool,
    ):
        """Insert or update a thread event object in the `google_cloud.yaml` file."""
        data = self.get_data()

        thread_event = get_from_dict(data, ["events", event, channel_id])

        if thread_event:
            if replace_reactions:
                thread_event["react_emojis"] = react_emojis
            else:
                thread_event["react_emojis"] = list(set(thread_event["react_emojis"]).union(set(react_emojis)))
        else:
            data["events"][event][channel_id] = {"ordered": ordered, "react_emojis": react_emojis}
        self.dump(data)

    def delete_thread_event(self, event: Literal["on_thread_create", "on_thread_update"], channel_id: int):
        """Delete a thread event object from the `google_cloud.yaml` file."""
        try:
            data = self.get_data()
            del data["events"][event][channel_id]
            self.dump(data=data)
            return True
        except:
            return False

    def dump(self, data):
        """Dump data into the `thread_events.yaml` file."""
        with open("src/data/thread_events.yaml", "w") as forum_events_file:
            yaml.dump(data, forum_events_file)
