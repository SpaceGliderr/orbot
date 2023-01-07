"""Publishes multiple messages to a Pub/Sub topic with an error handler."""
from concurrent import futures
from typing import Callable

from google.auth import jwt
from google.cloud import pubsub_v1
from google.oauth2 import service_account

project_id = "loonacord"
topic_id = "form-responses"

SCOPES = [
    "https://www.googleapis.com/auth/forms.body",
    "https://www.googleapis.com/auth/forms.responses.readonly",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/pubsub",
]

credentials = None
# if not credentials or credentials.invalid:
#     credentials = jwt.Credentials.from_service_account_file(
#         "service-account-info.json", audience="https://pubsub.googleapis.com/google.pubsub.v1.Publisher"
#     )
if not credentials or credentials.invalid:
    credentials = service_account.Credentials.from_service_account_file(
        "service-account-info.json",
        scopes=SCOPES,
        additional_claims={"audience": "https://pubsub.googleapis.com/google.pubsub.v1.Publisher"},
    )

publisher = pubsub_v1.PublisherClient(credentials=credentials)
topic_path = publisher.topic_path(project_id, topic_id)
print(topic_path)
publish_futures = []


def get_callback(
    publish_future: pubsub_v1.publisher.futures.Future, data: str
) -> Callable[[pubsub_v1.publisher.futures.Future], None]:
    def callback(publish_future: pubsub_v1.publisher.futures.Future) -> None:
        try:
            # Wait 60 seconds for the publish call to succeed.
            print(publish_future.result(timeout=60))
        except futures.TimeoutError:
            print(f"Publishing {data} timed out.")

    return callback


for i in range(2):
    data = str(i)
    # When you publish a message, the client returns a future.
    publish_future = publisher.publish(topic_path, data.encode("utf-8"))
    # Non-blocking. Publish failures are handled in the callback function.
    publish_future.add_done_callback(get_callback(publish_future, data))
    publish_futures.append(publish_future)

# Wait for all the publish futures to resolve before exiting.
futures.wait(publish_futures, return_when=futures.ALL_COMPLETED)

print(f"Published messages with error handler to {topic_path}.")
