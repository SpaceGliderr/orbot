import asyncio
import pprint
from http.client import HTTPException
from typing import Optional

import discord
from apiclient import discovery
from googleapiclient.errors import HttpError

from src.modules.auth.google_credentials import GoogleCredentials
from src.utils.helper import get_from_dict


class GoogleFormsService:
    def __init__(self, credentials) -> None:
        self.credentials = credentials
        self.service = discovery.build("forms", "v1", credentials=credentials)
        self.sheets_service = discovery.build("sheets", "v4", credentials=credentials)

    @classmethod
    def init_oauth(cls):
        return cls(GoogleCredentials.OAUTH2_CLIENT_ID_CRED)

    @classmethod
    def init_service_acc(cls):
        return cls(GoogleCredentials.get_service_acc_cred())

    def get_watch(
        self, form_id: str, event_type: str, topic_name: Optional[str] = None, watch_id: Optional[str] = None
    ):
        watch_list = self.service.forms().watches().list(formId=form_id).execute()
        print("WATCH LIST >>> ", watch_list)

        if watch_list == {}:
            return None

        def is_valid(watch: dict):
            if event_type and not watch["eventType"] == event_type:
                return False
            if topic_name and not get_from_dict(watch, ["target", "topic", "topicName"]) == topic_name:
                return False
            if watch_id and not watch["id"] == watch_id:
                return False
            return True

        result = next(
            (watch for watch in watch_list["watches"] if is_valid(watch)),
            None,
        )
        return result

    async def create_watch_list(
        self, form_id: str, event_type: str, interaction: discord.Interaction, topic_name: Optional[str] = None
    ):
        result = None
        topic_name = topic_name if topic_name else "projects/loonacord/topics/form-responses"
        print("CREDENTIALS >>> ", self.credentials)
        try:
            result = (
                self.service.forms()
                .watches()
                .create(
                    formId=form_id,
                    body={
                        "watch": {
                            "target": {"topic": {"topicName": "projects/loonacord/topics/form-responses"}},
                            "eventType": event_type,
                        }
                    },
                )
                .execute()
            )
            print("CREATE WATCH RESULT >>> ", result)
        except HttpError as err:
            print("ERROR >>> ", err)
            if err.status_code == 400:  # Means the particular form watch exists already
                result = self.get_watch(
                    form_id=form_id, event_type=event_type, topic_name="projects/loonacord/topics/form-responses"
                )
                print("GET WATCH RESULT >>> ", result)

                # loop = asyncio.get_event_loop()
                # asyncio.set_event_loop(loop)

                await interaction.followup.send(content="ALREADY FOUND THIS SHIT", ephemeral=True)

                # loop.run_until_complete(interaction.response.send_message(content="ALREADY FOUND THIS SHIT", ephemeral=True))
                # asyncio.run(interaction.response.send_message(content="ALREADY FOUND THIS SHIT", ephemeral=True))
        except:
            result = None

        print("WATCH RESULT >>> ", result)
        return result

    def get_latest_response(self, form_id: str, sheet_id: str):
        result = self.get_sheet(sheet_id)

        if result:
            questions = result["values"][0]
            answers = result["values"][-1]
            return [{str(question): answer} for question, answer in zip(questions, answers)]

        print("RESULT TITLE OF QUESTIONS >>> ", result["values"][0])
        print("LATEST RESPONSE >>> ", result["values"][-1])
        # pprint(result)

        result = self.service.forms().responses().list(formId=form_id).execute()
        print("RESULTS >>> ", result)
        if len(result) > 0:
            return result["responses"][0]
        return None

    def get_form_details(self, form_id: str):
        try:
            return self.service.forms().get(formId=form_id).execute()
        except:
            return None

    def get_sheet(self, sheet_id: str):
        print("SHEET ID >>> ", sheet_id)
        try:
            return (
                self.sheets_service.spreadsheets()
                .values()
                .get(spreadsheetId=sheet_id, range="Form Responses 1")
                .execute()
            )
        except:
            return None
