import asyncio
from typing import List, Optional, Union

import discord

from src.modules.ui.custom import PaginatedEmbedsView
from src.utils.config import GoogleCloudConfig
from src.utils.helper import get_from_dict


class GoogleFormsHelper:
    """A class comprised of static resources to handle visualizing responses from the Google Forms API."""

    # =================================================================================================================
    # FORM SCHEMA METHODS
    # =================================================================================================================
    @staticmethod
    def generate_schema(response: dict):
        """A method that generates a schema object to be stored in `google_cloud.yaml`.

        Parameters
        ----------
            * response: :class:`dict`
                - The API response for the form schema from the Google Forms API.
        """
        schema = {"info": response["info"], "questions": {}}

        # Set the corresponding Google Sheets ID if there is one created for the form
        linked_sheet_id = get_from_dict(response, ["linkedSheetId"])
        if linked_sheet_id:
            schema["linked_sheet_id"] = linked_sheet_id

        # Set the question ID and titles
        for question in response["items"]:
            question_id = get_from_dict(question, ["questionItem", "question", "questionId"])
            schema["questions"][question_id] = {"id": question_id, "title": question["title"]}

        return schema

    # =================================================================================================================
    # FORM RESPONSE METHODS
    # =================================================================================================================
    @staticmethod
    def generate_embed_from_response(
        form_id: str, answers: List[dict], embed_title: str, embed_description: Optional[str] = None
    ):
        """A method that generates an embed from a Google Forms response.

        Parameters
        ----------
            * form_id: :class:`str`
                - The Google Form ID.
            * answers: List[:class:`dict`]
                - The Google Forms response converted from JSON into a dictionary object.
            * embed_title: :class:`str`
            * embed_description: Optional[:class:`str`] | None
        """
        gc_conf = GoogleCloudConfig()
        embed = discord.Embed(title=embed_title, description=embed_description)

        for answer in answers:
            # Get the question title from the form schema
            question = gc_conf.get_question_details(form_id=form_id, question_id=answer["questionId"])

            # Set the question and response as a field
            embed.add_field(
                name=question["title"] if question else "_<No question title found>_",
                value=", ".join([answer_details["value"] for answer_details in answer["textAnswers"]["answers"]]),
                inline=False,
            )

        return embed

    @staticmethod
    def generate_embed_from_sheet(qnas: List[dict], embed_title: str, embed_description: Optional[str] = None):
        """A method that generates an embed of a Google Form response taken from the Google Sheet the form is linked to.

        Parameters
        ----------
            * qnas: List[:class:`dict`]
                - The question title and corresponding answers of the form response.
            * embed_title: :class:`str`
            * embed_description: Optional[:class:`str`] | None
        """
        embed = discord.Embed(title=embed_title, description=embed_description)

        for qna in qnas:
            answer = list(qna.values())[0]
            embed.add_field(
                name=list(qna.keys())[0], value=answer if answer != "" else "_<No response provided>_", inline=False
            )

        return embed

    @staticmethod
    def generate_form_response_embeds(form_id: str, response: Union[dict, List[dict]]):
        """A method that generates embeds from the answers in a form response. The form response can be obtained from the Google Forms API or Google Sheets.

        Parameters
        ----------
            * form_id: :class:`str`
                - The Google Form ID.
            * response: Union[:class:`dict`, :class:`List[dict]`]
                - The form response to convert into embeds.
                - A response with the `dict` object means that it originates from the Google Forms API; whereas a `List[dict]` object means it originates from Google Sheets.
        """
        schemas = GoogleCloudConfig().active_form_schemas  # Get all the active form schemas

        embed_title = get_from_dict(schemas, [form_id, "info", "title"])
        embed_description = get_from_dict(schemas, [form_id, "info", "description"])

        # Generate embeds based on the type of `response` object
        # - For each 25 answers, generate 1 embed (maximum fields for an embed is 25)
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
    async def broadcast_form_response_to_channel(
        form_id: str,
        form_response: Union[dict, List[dict]],
        broadcast_channel_id: int | str,
        client: discord.Client,
        client_loop: asyncio.AbstractEventLoop,
    ):
        """A method to send the generated form response embeds to a given Discord channel.

        Parameters
        ----------
            * form_id: :class:`str`
                - The Google Form ID.
            * form_response: Union[:class:`dict`, :class:`List[dict]`]
                - The API response of the form response.
            * broadcast_channel_id: :class:`int` | :class:`str`
                - The Discord channel ID to send the embeds to.
            * client: :class:`discord.Client`
                - The client instance that will be used to send messages.
            * client_loop: :class:`asyncio.AbstractEventLoop`
                - The main running event loop.
        """
        broadcast_channel = await client.fetch_channel(int(broadcast_channel_id))

        embeds = GoogleFormsHelper.generate_form_response_embeds(
            form_id=form_id, response=form_response["answers"] if isinstance(form_response, dict) else form_response
        )

        # Send using `run_coroutine_threadsafe` because it must be sent in the client loop instead of whatever thread it is running in
        asyncio.run_coroutine_threadsafe(
            broadcast_channel.send(
                embed=embeds[0], view=PaginatedEmbedsView(embeds=embeds) if len(embeds) > 1 else None
            ),
            client_loop,
        )

    # =================================================================================================================
    # EXPIRED FORM WATCH METHODS
    # =================================================================================================================
    @staticmethod
    def generate_expired_form_watch_embed(expired_watch: dict):
        """A method that generates an embed for expired form watches.

        Parameters
        ----------
            * expired_watch: :class:`dict`
                - The expired form watch object.
        """
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
        """A method that generates embeds for a list of expired form watches.

        Parameters
        ----------
            * expired_watches: List[:class:`dict`]
                - The list of expired form watch objects.
        """
        return [
            GoogleFormsHelper.generate_expired_form_watch_embed(expired_watch=expired_watch)
            for expired_watch in expired_watches
        ]
