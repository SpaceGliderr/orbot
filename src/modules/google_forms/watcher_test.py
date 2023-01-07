from __future__ import print_function

from apiclient import discovery
from google.auth import jwt
from google.auth.transport.requests import AuthorizedSession
from google.cloud import pubsub_v1
from google.oauth2 import service_account
from google_auth_oauthlib import flow
from httplib2 import Http
from oauth2client import client, file, tools

# from src.modules.auth.google_credentials import GoogleCredentials

# TODO: Try adding policy to bind the service account to the topic https://cloud.google.com/pubsub/docs/access-control#setting_a_policy
# project_id = "loonacord"
# topic_id = "form-responses"

# SCOPES = ["https://www.googleapis.com/auth/forms.body", "https://www.googleapis.com/auth/forms.responses.readonly", "https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/cloud-platform", "https://www.googleapis.com/auth/pubsub", "https://www.googleapis.com/auth/cloud-platform"]

# # store = file.Storage('token.json')
# credentials = None
# if not credentials or credentials.invalid:
#     credentials = service_account.Credentials.from_service_account_file("service-account-info.json", scopes=SCOPES)

# client = pubsub_v1.PublisherClient(credentials=credentials)

# topic_path = client.topic_path(project_id, topic_id)
# policy = client.get_iam_policy(request={"resource": topic_path})

# # Add all users as viewers.
# policy.bindings.add(role="roles/pubsub.viewer", members=["domain:google.com"])

# # Add a group as a publisher.
# policy.bindings.add(
#     role="roles/pubsub.publisher", members=["serviceAccount:orbot-888@loonacord.iam.gserviceaccount.com"]
# )

# # Set the policy
# policy = client.set_iam_policy(request={"resource": topic_path, "policy": policy})

# print("IAM policy for topic {} set: {}".format(topic_id, policy))

SCOPES = [
    "https://www.googleapis.com/auth/forms.body",
    # "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/pubsub",
]
# SCOPES = ["https://www.googleapis.com/auth/forms.body", "https://www.googleapis.com/auth/forms.responses.readonly", "https://www.googleapis.com/auth/drive"]
DISCOVERY_DOC = "https://forms.googleapis.com/$discovery/rest?version=v1"

auth_flow = flow.Flow.from_client_secrets_file(
    "oauth2-client-id.json",
    scopes=SCOPES,
    redirect_uri="urn:ietf:wg:oauth:2.0:oob",
)
authorization_url, _ = auth_flow.authorization_url(
    access_type="offline", include_granted_scopes="true", prompt="consent"
)
auth_code = input(f"Authorization URL: {authorization_url}\nEnter code: ")
auth_flow.fetch_token(code=auth_code)
credentials = auth_flow.credentials
print("CREDENTIALS >>> ", credentials.to_json())

# auth_url, auth_flow = GoogleCredentials.get_authorization_url()
# auth_code = input("Enter code: ")
# GoogleCredentials.set_oauth2_client_id_token(auth_flow, auth_code)
# print(GoogleCredentials.credentials_to_dict(GoogleCredentials.OAUTH2_CLIENT_ID_CRED))
# GoogleCredentials.save_credentials_to_file()

# store = file.Storage('token.json')
# credentials = None
# if not credentials or credentials.invalid:
#     flow = client.flow_from_clientsecrets('oauth2-client-id.json', SCOPES)
#     credentials = tools.run_flow(flow, store)
#     print(credentials.to_json())
# print({'token': credentials.token,
#       'refresh_token': credentials.refresh_token,
#       'token_uri': credentials.token_uri,
#       'client_id': credentials.client_id,
#       'client_secret': credentials.client_secret,
#       'scopes': credentials.scopes})

# store = file.Storage("token.json")
# credentials = None
# if not credentials or credentials.invalid:
#     credentials = service_account.Credentials.from_service_account_file(
#         "service-account-info.json",
#         scopes=SCOPES,
#         additional_claims={"audience": "https://pubsub.googleapis.com/google.pubsub.v1.Publisher"},
#     )
# credentials = jwt.Credentials.from_service_account_file("service-account-info.json", audience="https://pubsub.googleapis.com/google.pubsub.v1.Publisher")
# credentials.with_claims({"audience":"https://pubsub.googleapis.com/google.pubsub.v1.Publisher"})

# credentials = None
# if not credentials or credentials.invalid:
#     credentials = jwt.Credentials.from_service_account_file("service-account-info.json", audience="https://pubsub.googleapis.com/google.pubsub.v1.Publisher")


# form_service = discovery.build('forms', 'v1', http=AuthorizedSession(creds), discoveryServiceUrl=DISCOVERY_DOC, static_discovery=False)
form_service = discovery.build("forms", "v1", credentials=credentials)

# Request body for creating a form
NEW_FORM = {
    "info": {
        "title": "Quickstart form",
    }
}

# Request body to add a multiple-choice question
NEW_QUESTION = {
    "requests": [
        {
            "createItem": {
                "item": {
                    "title": "In what year did the United States land a mission on the moon?",
                    "questionItem": {
                        "question": {
                            "required": True,
                            "choiceQuestion": {
                                "type": "RADIO",
                                "options": [{"value": "1965"}, {"value": "1967"}, {"value": "1969"}, {"value": "1971"}],
                                "shuffle": True,
                            },
                        }
                    },
                },
                "location": {"index": 0},
            }
        }
    ]
}

# result = form_service.forms().get(formId="1bB61z96WS2uv7nql2bV1YDwBG1L0tH6F6yBJTUfWY_I").execute()
# print(result)

# result = form_service.forms().responses().list(formId="1T-xKO6gC9L5Nl8m40hv0oteA2R-20u8TN8CWXayVnaA").execute()
# print(result)

body = {
    "watch": {
        "target": {
            "topic": {"topicName": "projects/loonacord/topics/form-responses"},
        },
        "eventType": "RESPONSES",
    },
}
# result = (
#     form_service.forms().watches().create(formId="1T-xKO6gC9L5Nl8m40hv0oteA2R-20u8TN8CWXayVnaA", body=body).execute()
# )
# print(result)
# result = form_service.forms().watches().list(formId="1T-xKO6gC9L5Nl8m40hv0oteA2R-20u8TN8CWXayVnaA").execute()
# print(result)
result = (
    form_service.forms()
    .watches()
    .delete(formId="1T-xKO6gC9L5Nl8m40hv0oteA2R-20u8TN8CWXayVnaA", watchId="54e2f6f9-b1bd-4e4d-aaba-da9fc77866d7")
    .execute()
)
print(result)
# result = form_service.forms().watches().list(formId="1T-xKO6gC9L5Nl8m40hv0oteA2R-20u8TN8CWXayVnaA").execute()
# print(result)

# Creates the initial form
# result = form_service.forms().create(body=NEW_FORM).execute()

# # Adds the question to the form
# question_setting = form_service.forms().batchUpdate(formId=result["formId"], body=NEW_QUESTION).execute()

# # Prints the result to show the question has been added
# get_result = form_service.forms().get(formId="1T-xKO6gC9L5Nl8m40hv0oteA2R-20u8TN8CWXayVnaA").execute()
# print(get_result)
