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
    def __init__(
        self,
        message: pubsub_v1.subscriber.message.Message,
        client: discord.Client,
        client_loop: asyncio.AbstractEventLoop,
    ):
        self.message = message
        self.form_service = GoogleFormsService.init_service_acc()
        self.client = client
        self.client_loop = client_loop

    def form_watch_callback(self, form_id: str, watch_id: str, event_type: Literal["RESPONSES", "SCHEMA"]):
        form_schema = get_from_dict(GoogleCloudConfig().active_form_schemas, [form_id])

        if not form_schema:
            form_details = self.form_service.get_form_details(form_id=form_id)

            if form_details:
                form_schema = GoogleFormsHelper.generate_schema(response=form_details)
                GoogleCloudConfig().upsert_form_schema(form_id=form_id, schema=form_schema)
            else:
                raise Exception("Failed to retrieve schema")

        latest_response = self.form_service.get_latest_form_response(
            form_id=form_id, sheet_id=get_from_dict(form_schema, ["linked_sheet_id"])
        )
        _, watch = GoogleCloudConfig().search_active_form_watch(
            form_id=form_id, watch_id=watch_id, event_type=event_type
        )

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

    def execute(self):
        form_id = get_from_dict(self.message.attributes, ["formId"])
        watch_id = get_from_dict(self.message.attributes, ["watchId"])
        event_type = get_from_dict(self.message.attributes, ["eventType"])

        if form_id and watch_id and event_type:
            self.form_watch_callback(form_id=form_id, watch_id=watch_id, event_type=event_type)


class GoogleTopicListenerThread(threading.Thread):
    def __init__(self, topic_subscription_path: str, client: discord.Client, client_loop: asyncio.AbstractEventLoop):
        threading.Thread.__init__(self)

        self.topic_subscription_path = topic_subscription_path
        self.client = client
        self.client_loop = client_loop

        self.subscriber = pubsub_v1.SubscriberClient(credentials=GoogleCredentialsHelper.service_acc_cred())
        self.stream = None

    def callback(self, message: pubsub_v1.subscriber.message.Message):
        message.ack()
        GoogleTopicHandler(message=message, client=self.client, client_loop=self.client_loop).execute()

    def run(self):
        logging.info(f"Listener started for {self.topic_subscription_path}")
        self.stream = self.subscriber.subscribe(subscription=self.topic_subscription_path, callback=self.callback)
        self.stream.result()

    def close(self):
        self.stream.cancel()
        self.stream.result()
        self.subscriber.close()
        logging.info(f"Listener for {self.topic_subscription_path} was closed successfully")


class GoogleTopicListenerManager:
    def __init__(self, topic_names: List[str], client: discord.Client, client_loop: asyncio.AbstractEventLoop):
        self.listener_threads = {
            topic_subscription_path: GoogleTopicListenerThread(
                topic_subscription_path=topic_subscription_path, client=client, client_loop=client_loop
            )
            for topic_subscription_path in topic_names
        }

    @classmethod
    def init_and_run(cls, topic_names: List[str], client: discord.Client, client_loop: asyncio.AbstractEventLoop):
        manager = cls(topic_names=topic_names, client=client, client_loop=client_loop)
        manager.start_listeners()
        return manager

    def start_listeners(self):
        for _, listener in self.listener_threads.items():
            listener.start()

    def start_stream(
        self, topic_subscription_path: str, client: discord.Client, client_loop: asyncio.AbstractEventLoop
    ):
        existing_thread = get_from_dict(self.listener_threads, [topic_subscription_path])

        if existing_thread:
            if not existing_thread.is_alive():
                del self.listener_threads[topic_subscription_path]
            return

        # Add subscription
        self.listener_threads[topic_subscription_path] = GoogleTopicListenerThread(
            topic_subscription_path=topic_subscription_path, client=client, client_loop=client_loop
        )
        self.listener_threads[topic_subscription_path].run()

    def close_stream(self, topic_subscription_path: str):
        stream = get_from_dict(self.listener_threads, topic_subscription_path)

        if stream:
            stream.close()
        else:
            raise Exception("No stream with the provided topic subscription path was found")

    def close_all_streams(self):
        for topic_subscription_path, listener_thread in self.listener_threads.items():
            if listener_thread.is_alive():
                listener_thread.close()
            else:
                logging.info(f"Listener for {topic_subscription_path} is already closed")
