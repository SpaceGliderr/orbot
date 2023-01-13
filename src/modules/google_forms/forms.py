import asyncio
from typing import List, Optional, Union

import discord

from src.modules.ui.custom import PaginatedEmbedsView
from src.utils.config import GoogleCloudConfig
from src.utils.helper import get_from_dict


class GoogleFormsHelper:
    @staticmethod
    def generate_embed_from_response(
        form_id: str, answers: List[dict], embed_title: str, embed_description: Optional[str] = None
    ):
        gc_conf = GoogleCloudConfig()
        embed = discord.Embed(title=embed_title, description=embed_description)

        for answer in answers:
            question = gc_conf.get_question_details(form_id=form_id, question_id=answer["questionId"])

            embed.add_field(
                name=question["title"] if question else "_<No question title found>_",
                value=", ".join([answer_details["value"] for answer_details in answer["textAnswers"]["answers"]]),
                inline=False,
            )

        return embed

    @staticmethod
    def generate_embed_from_sheet(qnas: List[dict], embed_title: str, embed_description: Optional[str] = None):
        embed = discord.Embed(title=embed_title, description=embed_description)

        for qna in qnas:
            answer = list(qna.values())[0]
            embed.add_field(
                name=list(qna.keys())[0], value=answer if answer != "" else "_<No response provided>_", inline=False
            )

        return embed

    @staticmethod
    def generate_form_response_embeds(form_id: str, response: Union[dict, List[dict]]):
        schemas = GoogleCloudConfig().active_form_schemas

        embed_title = get_from_dict(schemas, [form_id, "info", "title"])
        embed_description = get_from_dict(schemas, [form_id, "info", "description"])

        return [
            GoogleFormsHelper.generate_embed_from_response(
                form_id=form_id,
                answers=list(response.values())[i : i + 25],
                embed_title=embed_title,
                embed_description=embed_description,
            )
            if isinstance(response, dict)
            else GoogleFormsHelper.generate_embed_from_sheet(
                qnas=response[i : i + 25], embed_title=embed_title, embed_description=embed_description
            )
            for i in range(0, len(response), 25)
        ]

    @staticmethod
    def generate_schema(response: dict):
        schema = {"info": response["info"], "questions": {}}

        linked_sheet_id = get_from_dict(response, ["linkedSheetId"])

        if linked_sheet_id:
            schema["linked_sheet_id"] = linked_sheet_id

        for question in response["items"]:
            question_id = get_from_dict(question, ["questionItem", "question", "questionId"])
            schema["questions"][question_id] = {"id": question_id, "title": question["title"]}

        return schema

    @staticmethod
    async def broadcast_form_response_to_channel(
        form_id: str,
        form_response: Union[dict, List[dict]],
        broadcast_channel_id: int | str,
        client: discord.Client,
        client_loop: asyncio.AbstractEventLoop,
    ):
        broadcast_channel = await client.fetch_channel(int(broadcast_channel_id))

        embeds = GoogleFormsHelper.generate_form_response_embeds(
            form_id=form_id, response=form_response["answers"] if isinstance(form_response, dict) else form_response
        )

        asyncio.run_coroutine_threadsafe(
            broadcast_channel.send(
                embed=embeds[0], view=PaginatedEmbedsView(embeds=embeds) if len(embeds) > 1 else None
            ),
            client_loop,
        )

    @staticmethod
    def generate_expired_form_watch_embed(expired_watch: dict):
        embed = discord.Embed(
            title="Form Watch Expired",
            description=f"A form watch with the form ID of {expired_watch['form_id']} has expired. Please create a new watch with the same form ID instead.\nHere are the details for the expired form watch:",
        )

        embed.add_field(name="Form ID", value=expired_watch["form_id"], inline=False)
        embed.add_field(name="Watch ID", value=expired_watch["watch_id"], inline=False)
        embed.add_field(name="Event Type", value=expired_watch["event_type"])
        embed.add_field(name="Broadcast Channel", value=f"<#{expired_watch['broadcast_channel_id']}>")

        return embed

    @staticmethod
    def generate_expired_form_watch_embeds(expired_watches: List[dict]):
        return [
            GoogleFormsHelper.generate_expired_form_watch_embed(expired_watch=expired_watch)
            for expired_watch in expired_watches
        ]
