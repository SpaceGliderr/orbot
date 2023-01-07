from concurrent.futures import TimeoutError

from apiclient import discovery
from google.auth import jwt
from google.cloud import pubsub_v1
from google.oauth2 import service_account

project_id = "loonacord"
subscription_id = "form-responses-sub"
# timeout = 20

# store = file.Storage('token.json')
SCOPES = [
    "https://www.googleapis.com/auth/forms.body",
    "https://www.googleapis.com/auth/forms.responses.readonly",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/pubsub",
]

credentials = None
if not credentials or credentials.invalid:
    # credentials = jwt.Credentials.from_service_account_file(
    #     "service-account-info.json", audience="https://pubsub.googleapis.com/google.pubsub.v1.Subscriber"
    # )
    credentials = service_account.Credentials.from_service_account_file(
        "service-account-info.json",
        scopes=SCOPES,
        additional_claims={"audience": "https://pubsub.googleapis.com/google.pubsub.v1.Subscriber"},
    )

subscriber = pubsub_v1.SubscriberClient(credentials=credentials)
# The `subscription_path` method creates a fully qualified identifier
# in the form `projects/{project_id}/subscriptions/{subscription_id}`
subscription_path = subscriber.subscription_path(project_id, subscription_id)

form_service = discovery.build("forms", "v1", credentials=credentials)


def callback(message: pubsub_v1.subscriber.message.Message) -> None:
    print(f"Received {message}.")
    # print(message.attributes)
    result = form_service.forms().responses().list(formId=message.attributes["formId"]).execute()
    print(result["responses"][-1])
    message.ack()


streaming_pull_future = subscriber.subscribe(subscription_path, callback=callback)
print(f"Listening for messages on {subscription_path}..\n")

# Wrap subscriber in a 'with' block to automatically call close() when done.
with subscriber:
    try:
        # When `timeout` is not set, result() will block indefinitely,
        # unless an exception is encountered first.
        streaming_pull_future.result()
        # streaming_pull_future.result(timeout=timeout)
    except (TimeoutError, KeyboardInterrupt) as err:
        streaming_pull_future.cancel()  # Trigger the shutdown.
        streaming_pull_future.result()  # Block until the shutdown is complete.

        print("SHUT DOWN")
