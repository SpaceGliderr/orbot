from concurrent.futures import TimeoutError
from google.cloud import pubsub_v1
from google.auth import jwt

project_id = "loonacord"
subscription_id = "form-responses-sub"
timeout = 20

# store = file.Storage('token.json')
credentials = None
if not credentials or credentials.invalid:
    credentials = jwt.Credentials.from_service_account_file("service-account-info.json", audience="https://pubsub.googleapis.com/google.pubsub.v1.Subscriber")

subscriber = pubsub_v1.SubscriberClient(credentials=credentials)
# The `subscription_path` method creates a fully qualified identifier
# in the form `projects/{project_id}/subscriptions/{subscription_id}`
subscription_path = subscriber.subscription_path(project_id, subscription_id)

def callback(message: pubsub_v1.subscriber.message.Message) -> None:
    print(f"Received {message}.")
    message.ack()

streaming_pull_future = subscriber.subscribe(subscription_path, callback=callback)
print(f"Listening for messages on {subscription_path}..\n")

# Wrap subscriber in a 'with' block to automatically call close() when done.
with subscriber:
    try:
        # When `timeout` is not set, result() will block indefinitely,
        # unless an exception is encountered first.
        streaming_pull_future.result(timeout=timeout)
    except (TimeoutError, KeyboardInterrupt) as err:
        streaming_pull_future.cancel()  # Trigger the shutdown.
        streaming_pull_future.result()  # Block until the shutdown is complete.

        print("SHUT DOWN")
