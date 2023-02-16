from typing import Literal, Optional

from apiclient import discovery
from googleapiclient.errors import HttpError

from src.modules.auth.google_credentials import GoogleCredentialsHelper
from src.utils.helper import get_from_dict


class GoogleFormsService:
    """A class providing methods that handle executing the Google Forms API.

    Parameters
    ----------
        * credentials: :class:`credentials.Credentials`
            - A Google Credential object.
    """

    def __init__(self, credentials) -> None:
        self.credentials = credentials
        self.forms_service = discovery.build("forms", "v1", credentials=credentials, cache_discovery=False)
        self.sheets_service = discovery.build("sheets", "v4", credentials=credentials, cache_discovery=False)

    @classmethod
    def init_service_acc(cls):
        """An initialization method to initialize the service with service account credentials."""
        return cls(GoogleCredentialsHelper.service_acc_cred())

    # =================================================================================================================
    # FORM DETAIL METHODS
    # =================================================================================================================
    def get_form_details(self, form_id: str):
        """A method that utilizes the `get` request from the Google Forms API to obtain details of a form.

        Parameters
        ----------
            * form_id: :class:`str`
                - The Google Form ID to use the request on.
        """
        try:
            return self.forms_service.forms().get(formId=form_id).execute()
        except:
            return None

    # =================================================================================================================
    # FORM WATCH METHODS
    # =================================================================================================================
    def get_form_watches(self, form_id: str):
        """A method that utilizes the `watches.list` request from the Google Forms API to obtain all form watches.

        Parameters
        ----------
            * form_id: :class:`str`
                - The Google Form ID to use the request on.
        """
        form_watches = self.forms_service.forms().watches().list(formId=form_id).execute()
        return form_watches if form_watches != {} else None

    def filter_form_watch(
        self,
        form_id: str,
        watch_id: Optional[str] = None,
        event_type: Optional[Literal["RESPONSES", "SCHEMA"]] = None,
        topic_name: Optional[str] = None,
    ):
        """A method that filters for a specific form watch.

        Parameters
        ----------
            * form_id: :class:`str`
                - The Google Form ID to use the request on.
            * watch_id: Optional[:class:`str`] | None
                - The watch ID to search for.
            * event_type: Optional[:class:`Literal["RESPONSES", "SCHEMA"]`] | None
                - The watch event to search for.
            * topic_name: Optional[:class:`str`] | None
                - The topic name that the watch is assigned to.
        """
        form_watches = self.get_form_watches(form_id=form_id)  # Get a list of form watches for the specific form
        if form_watches:
            # Filter the list of form watches based on the filters
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
        """A method that utilizes the `watches.create` request from the Google Forms API to create a form watch.

        Parameters
        ----------
            * form_id: :class:`str`
                - The Google Form ID to use the request on.
            * event_type: :class:`Literal["RESPONSES", "SCHEMA"]
                - The watch event to create.
            * topic_name: :class:`str`
                - The topic name to assign the watch to.
        """
        form_watch = None
        try:  # Use the `watches.create` request
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
            if (
                err.status_code == 400
            ):  # The HTTP error means that a form watch already exists, so we should get the existing form watch
                form_watch = self.filter_form_watch(form_id=form_id, event_type=event_type, topic_name=topic_name)
        except Exception as err:
            form_watch = None

        return form_watch

    def delete_form_watch(self, form_id: str, watch_id: str):
        """A method that utilizes the `watches.delete` request from the Google Forms API to delete a form watch.

        Parameters
        ----------
            * form_id: :class:`str`
                - The Google Form ID to use the request on.
            * watch_id: :class:`str`
                - The watch ID to delete.
        """
        try:
            return self.forms_service.forms().watches().delete(formId=form_id, watchId=watch_id).execute()
        except:
            return None

    def renew_form_watch(self, form_id: str, watch_id: str):
        """A method that utilizes the `watches.renew` request from the Google Forms API to renew a form watch.

        Parameters
        ----------
            * form_id: :class:`str`
                - The Google Form ID to use the request on.
            * watch_id: :class:`str`
                - The watch ID to renew.
        """
        try:
            return self.forms_service.forms().watches().renew(formId=form_id, watchId=watch_id).execute()
        except:
            return None

    # =================================================================================================================
    # FORM RESPONSE METHODS
    # =================================================================================================================
    def get_sheet(self, sheet_id: str, cell_range: str = "Form Responses 1"):
        """A method that utilizes the `get` request from the Google Sheets API to get the contents of a sheet.

        Parameters
        ----------
            * form_id: :class:`str`
                - The Google Form ID to use the request on.
            * watch_id: :class:`str`
                - The watch ID to search for.
        """
        try:
            return self.sheets_service.spreadsheets().values().get(spreadsheetId=sheet_id, range=cell_range).execute()
        except:
            return None

    def get_latest_form_response(self, form_id: str, sheet_id: str):
        """A method that obtains the latest form response from a linked Google Sheet or from the Google Forms API.

        Parameters
        ----------
            * form_id: :class:`str`
                - The Google Form ID to use the request on.
            * sheet_id: :class:`str`
                - The Google Sheet ID to obtain the latest form response from.
        """
        # Use Google Sheets API to get the latest response
        sheet = self.get_sheet(sheet_id)
        sheet_responses = get_from_dict(sheet, ["values"])

        if sheet_responses and len(sheet_responses) > 1:
            questions = sheet_responses[0]
            answers = sheet_responses[-1]
            return [{str(question): answer} for question, answer in zip(questions, answers)]

        # Use Google Forms API to get the latest response
        form_responses = self.forms_service.forms().responses().list(formId=form_id).execute()
        return (
            max(form_responses["responses"], key=lambda response: response["lastSubmittedTime"])
            if len(form_responses) > 0
            else None
        )
