import asyncio
import logging
import threading
from typing import List, Literal

import discord
from google.cloud import pubsub_v1

from src.modules.auth.google_credentials import GoogleCredentialsHelper
from src.modules.google_forms.forms import GoogleFormsHelper
from src.modules.google_forms.service import GoogleFormsService
from src.utils.config import GoogleCloudConfig
from src.utils.helper import get_from_dict


class GoogleTopicHandler:
    """A class providing methods that handle the response from a Google Topic.

    Parameters
    ----------
        * message: :class:`pubsub_v1.subscriber.message.Message`
            - The response of the Google Topic.
        * client: :class:`discord.Client`
            - The client instance that will be used to send messages.
        * client_loop: :class:`asyncio.AbstractEventLoop`
            - The main running event loop.
    """

    def __init__(
        self,
        message: pubsub_v1.subscriber.message.Message,
        client: discord.Client,
        client_loop: asyncio.AbstractEventLoop,
    ):
        self.message = message
        self.client = client
        self.client_loop = client_loop

        self.form_service = GoogleFormsService.init_service_acc()

    async def on_form_watch_error(
        self,
        form_id: str,
        watch_id: str,
        broadcast_channel_id: int | str,
        client: discord.Client,
        client_loop: asyncio.AbstractEventLoop,
    ):
        """A method used to handle the errors thrown when the `on_form_watch_error` is called."""
        broadcast_channel = await client.fetch_channel(int(broadcast_channel_id))

        # Send using `run_coroutine_threadsafe` because it must be sent in the client loop instead of whatever thread it is running in
        asyncio.run_coroutine_threadsafe(
            broadcast_channel.send(
                content=f"Failed to retrieve form response with form ID of `{form_id}` and watch ID of `{watch_id}`. Please check with the developer or check the permissions of the Google Form or Google Sheets."
            ),
            client_loop,
        )

    def form_watch_callback(self, form_id: str, watch_id: str):
        """A callback method that handles the form watch response from the subscribed Google Topic. Sends a notification to the broadcast channel based on the received form watch response.

        Parameters
        ----------
            * form_id: :class:`str`
            * watch_id: :class:`str`
            * event_type: :class:`Literal["RESPONSES", "SCHEMA"]`
        """
        # Obtain the form schema
        form_schema = get_from_dict(GoogleCloudConfig().active_form_schemas, [form_id])

        if not form_schema:  # If no form schema was saved prior, try retrieving the form schema
            form_details = self.form_service.get_form_details(form_id=form_id)

            if form_details:
                form_schema = GoogleFormsHelper.generate_schema(response=form_details)
                GoogleCloudConfig().upsert_form_schema(form_id=form_id, schema=form_schema)
            else:
                raise Exception("Failed to retrieve schema")

        # Obtain the latest response for the form
        try:
            latest_response = self.form_service.get_latest_form_response(
                form_id=form_id, sheet_id=get_from_dict(form_schema, ["linked_sheet_id"])
            )

            # Obtain the form watch details
            _, watch = GoogleCloudConfig().search_active_form_watch(
                form_id=form_id, watch_id=watch_id, event_type="RESPONSES"
            )

            # Broadcast the notification to the Discord channel
            asyncio.run_coroutine_threadsafe(
                GoogleFormsHelper.broadcast_form_response_to_channel(
                    form_id=form_id,
                    form_response=latest_response,
                    broadcast_channel_id=watch["broadcast_channel_id"],
                    client=self.client,
                    client_loop=self.client_loop,
                ),
                self.client_loop,
            )
        except:
            asyncio.run_coroutine_threadsafe(
                self.on_form_watch_error(
                    form_id=form_id,
                    watch_id=watch_id,
                    broadcast_channel_id=GoogleCloudConfig().form_channel_id,
                    client=self.client,
                    client_loop=self.client_loop,
                )
            )

    def form_schema_callback(self, form_id: str, watch_id: str):
        """A callback method that handles the form schema response from the subscribed Google Topic. Sends a notification to the broadcast channel based on the received form schema response.

        Parameters
        ----------
            * form_id: :class:`str`
            * watch_id: :class:`str`
        """
        form_details = self.form_service.get_form_details(form_id=form_id)
        if not form_details:
            raise Exception("Failed to retrieve form details")

        schema = GoogleFormsHelper.generate_schema(response=form_details)
        GoogleCloudConfig().upsert_form_schema(form_id=form_id, schema=schema)

        _, watch = GoogleCloudConfig().search_active_form_watch(form_id=form_id, watch_id=watch_id, event_type="SCHEMA")

        asyncio.run_coroutine_threadsafe(
            GoogleFormsHelper.broadcast_form_schema_to_channel(
                form_id=form_id,
                form_schema=schema,
                broadcast_channel_id=watch["broadcast_channel_id"],
                client=self.client,
                client_loop=self.client_loop,
            ),
            self.client_loop,
        )

    def execute(self):
        """A method that extracts relevant information from the Google Topic response and triggers the `form_watch_callback` method."""
        attributes = {
            k: v for k, v in self.message.attributes.items()
        }  # Convert the attributes `ScalarMapContainer` into `dict`

        form_id = get_from_dict(attributes, ["formId"])
        watch_id = get_from_dict(attributes, ["watchId"])
        event_type = get_from_dict(attributes, ["eventType"])

        if form_id and watch_id and event_type and event_type == "RESPONSES":
            self.form_watch_callback(form_id=form_id, watch_id=watch_id)
        elif form_id and watch_id and event_type and event_type == "SCHEMA":
            self.form_schema_callback(form_id=form_id, watch_id=watch_id)


class GoogleTopicListenerThread(threading.Thread):
    """A class that spawns a thread to listen to a Google Topic. A thread is required to listen to the topic to avoid blocking the main Discord event loop.

    Parameters
    ----------
        * topic_subscription_path: :class:`str`
            - The topic name to listen to.
        * client: :class:`discord.Client`
            - The client instance that will be used to send messages.
        * client_loop: :class:`asyncio.AbstractEventLoop`
            - The main running event loop.
    """

    def __init__(self, topic_subscription_path: str, client: discord.Client, client_loop: asyncio.AbstractEventLoop):
        threading.Thread.__init__(self)

        self.topic_subscription_path = topic_subscription_path
        self.client = client
        self.client_loop = client_loop

        self.subscriber = pubsub_v1.SubscriberClient(credentials=GoogleCredentialsHelper.service_acc_cred())
        self.stream = None

    def callback(self, message: pubsub_v1.subscriber.message.Message):
        """A callback that receives responses from the subscribed Google Topic.

        Parameters
        ----------
            * message: :class:`pubsub_v1.subscriber.message.Message`
                - The response of the Google Topic.
        """
        message.ack()
        print("Message >>> ", message)
        GoogleTopicHandler(message=message, client=self.client, client_loop=self.client_loop).execute()

    def run(self):
        """Overrides the `run` method of the thread. Used to start the thread."""
        logging.info(f"Listener started for {self.topic_subscription_path}")
        self.stream = self.subscriber.subscribe(subscription=self.topic_subscription_path, callback=self.callback)
        self.stream.result()

    def close(self):
        """A method to close the thread and its corresponding streams."""
        self.stream.cancel()
        self.stream.result()
        self.subscriber.close()
        logging.info(f"Listener for {self.topic_subscription_path} was closed successfully")


class GoogleTopicListenerManager:
    """A class providing methods that handle instances of the `GoogleTopicListenerThread`.

    Parameters
    ----------
        * topic_names: List[:class:`str`]
            - The list of topic names to listen to.
        * client: :class:`discord.Client`
        * client_loop: :class:`asyncio.AbstractEventLoop`
            - Needed to by the `GoogleTopicListenerThread`.
    """

    def __init__(self, topic_names: List[str], client: discord.Client, client_loop: asyncio.AbstractEventLoop):
        self.listener_threads = {
            topic_subscription_path: GoogleTopicListenerThread(
                topic_subscription_path=topic_subscription_path, client=client, client_loop=client_loop
            )
            for topic_subscription_path in topic_names
        }

    @classmethod
    def init_and_run(cls, topic_names: List[str], client: discord.Client, client_loop: asyncio.AbstractEventLoop):
        """An initialization method to initialize the manager with the listener threads and start them."""
        manager = cls(topic_names=topic_names, client=client, client_loop=client_loop)
        manager.start_listeners()
        return manager

    def start_listeners(self):
        """A method that starts the listener threads."""
        for _, listener in self.listener_threads.items():
            listener.start()

    def start_stream(
        self, topic_subscription_path: str, client: discord.Client, client_loop: asyncio.AbstractEventLoop
    ):
        """A method that creates a topic listener thread and starts it.

        Parameters
        ----------
            * topic_subscription_path: :class:`str`
                - The topic name to create a .
            * client: :class:`discord.Client`
            * client_loop: :class:`asyncio.AbstractEventLoop`
        """
        # Check for any existing inactive threads for the topic_subscription_path
        existing_thread = get_from_dict(self.listener_threads, [topic_subscription_path])

        if existing_thread:
            if not existing_thread.is_alive():  # If there are inactive threads, remove the thread instance
                del self.listener_threads[topic_subscription_path]
            else:
                return

        # Create thread listener and start the listener
        self.listener_threads[topic_subscription_path] = GoogleTopicListenerThread(
            topic_subscription_path=topic_subscription_path, client=client, client_loop=client_loop
        )
        self.listener_threads[topic_subscription_path].start()

    def close_stream(self, topic_subscription_path: str):
        """A method that searches for a topic listener thread and closes it.

        Parameters
        ----------
            * topic_subscription_path: :class:`str`
                - The topic name to unsubscribe from.
        """
        # Find the listener thread
        stream = get_from_dict(self.listener_threads, [topic_subscription_path])

        if stream:
            stream.close()  # Close the thread
        else:
            raise Exception("No stream with the provided topic subscription path was found")

    def close_all_streams(self):
        """A method that closes all active topic listener threads."""
        for topic_subscription_path, listener_thread in self.listener_threads.items():
            if listener_thread.is_alive():
                listener_thread.close()
            else:
                logging.info(f"Listener for {topic_subscription_path} is already closed")
