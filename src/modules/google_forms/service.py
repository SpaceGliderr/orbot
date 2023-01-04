from typing import Literal, Optional

import discord
from apiclient import discovery
from googleapiclient.errors import HttpError

from src.modules.auth.google_credentials import GoogleCredentials
from src.utils.helper import get_from_dict


class GoogleFormsService:
    def __init__(self, credentials) -> None:
        self.credentials = credentials
        self.forms_service = discovery.build("forms", "v1", credentials=credentials)
        self.sheets_service = discovery.build("sheets", "v4", credentials=credentials)

    @classmethod
    def init_oauth(cls):
        return cls(GoogleCredentials.OAUTH2_CLIENT_ID_CRED)

    @classmethod
    def init_service_acc(cls):
        return cls(GoogleCredentials.get_service_acc_cred())

    def get_form_details(self, form_id: str):
        try:
            return self.forms_service.forms().get(formId=form_id).execute()
        except:
            return None

    def get_form_watches(self, form_id: str):
        form_watches = self.forms_service.forms().watches().list(formId=form_id).execute()
        return form_watches if form_watches != {} else None

    def filter_form_watch(
        self,
        form_id: str,
        watch_id: Optional[str] = None,
        event_type: Optional[Literal["RESPONSES", "SCHEMA"]] = None,
        topic_name: Optional[str] = None,
    ):
        form_watches = self.get_form_watches(form_id=form_id)
        if form_watches:
            return next(
                list(
                    filter(
                        lambda watch: False
                        if watch_id and not watch["id"] == watch_id
                        else False
                        if event_type and not watch["event_type"] == event_type
                        else False
                        if topic_name and not get_from_dict(watch, ["target", "topic", "topicName"]) == topic_name
                        else True,
                        form_watches["watches"],
                    )
                ),
                None,
            )
        return None

    def create_form_watch(self, form_id: str, event_type: Literal["RESPONSES", "SCHEMA"], topic_name: str):
        form_watch = None

        try:
            form_watch = (
                self.forms_service.forms()
                .watches()
                .create(
                    formId=form_id,
                    body={
                        "watch": {
                            "target": {"topic": {"topicName": topic_name}},
                            "eventType": event_type,
                        }
                    },
                )
                .execute()
            )
        except HttpError as err:
            if err.status_code == 400:
                form_watch = self.filter_form_watch(form_id=form_id, event_type=event_type, topic_name=topic_name)
        except Exception as err:
            form_watch = None

        return form_watch

    def delete_form_watch(self, form_id: str, watch_id: str):
        try:
            return self.forms_service.forms().watches().delete(formId=form_id, watchId=watch_id).execute()
        except:
            return None

    def get_sheet(self, sheet_id: str, cell_range: str = "Form Responses 1"):
        try:
            return self.sheets_service.spreadsheets().values().get(spreadsheetId=sheet_id, range=cell_range).execute()
        except:
            return None

    def get_latest_form_response(self, form_id: str, sheet_id: str):
        sheet = self.get_sheet(sheet_id)
        sheet_responses = get_from_dict(sheet, ["values"])

        if sheet_responses and len(sheet_responses) > 1:
            questions = sheet_responses[0]
            answers = sheet_responses[-1]
            return [{str(question): answer} for question, answer in zip(questions, answers)]

        form_responses = self.forms_service.forms().responses().list(formId=form_id).execute()
        return form_responses["responses"][0] if len(form_responses) > 0 else None
