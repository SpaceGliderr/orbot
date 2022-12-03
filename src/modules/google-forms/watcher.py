from __future__ import print_function

from apiclient import discovery
from httplib2 import Http
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

SCOPES = ["https://www.googleapis.com/auth/forms.body", "https://www.googleapis.com/auth/forms.responses.readonly", "https://www.googleapis.com/auth/drive"]
DISCOVERY_DOC = "https://forms.googleapis.com/$discovery/rest?version=v1"

# store = file.Storage('token.json')
creds = None
if not creds or creds.invalid:
    # flow = client.flow_from_clientsecrets('src/credentials.json', SCOPES)
    # creds = tools.run_flow(flow, store)
    creds = service_account.Credentials.from_service_account_file("service-account-info.json", scopes=SCOPES)


# form_service = discovery.build('forms', 'v1', http=AuthorizedSession(creds), discoveryServiceUrl=DISCOVERY_DOC, static_discovery=False)
form_service = discovery.build('forms', 'v1', credentials=creds)

# Request body for creating a form
NEW_FORM = {
    "info": {
        "title": "Quickstart form",
    }
}

# Request body to add a multiple-choice question
NEW_QUESTION = {
    "requests": [{
        "createItem": {
            "item": {
                "title": "In what year did the United States land a mission on the moon?",
                "questionItem": {
                    "question": {
                        "required": True,
                        "choiceQuestion": {
                            "type": "RADIO",
                            "options": [
                                {"value": "1965"},
                                {"value": "1967"},
                                {"value": "1969"},
                                {"value": "1971"}
                            ],
                            "shuffle": True
                        }
                    }
                },
            },
            "location": {
                "index": 0
            }
        }
    }]
}

# result = form_service.forms().get(formId="1bB61z96WS2uv7nql2bV1YDwBG1L0tH6F6yBJTUfWY_I").execute()
# print(result)

result = form_service.forms().responses().list(formId="1bB61z96WS2uv7nql2bV1YDwBG1L0tH6F6yBJTUfWY_I").execute()
print(result)

# Creates the initial form
# result = form_service.forms().create(body=NEW_FORM).execute()

# # Adds the question to the form
# question_setting = form_service.forms().batchUpdate(formId=result["formId"], body=NEW_QUESTION).execute()

# # Prints the result to show the question has been added
# get_result = form_service.forms().get(formId=result["formId"]).execute()
# print(get_result)