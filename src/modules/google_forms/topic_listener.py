import asyncio
import logging
import threading
from typing import List

import discord
from google.cloud import pubsub_v1

from src.utils.helper import get_from_dict


class GoogleTopicListenerThread(threading.Thread):
    def __init__(
        self, topic_subscription_path: str, credentials, client: discord.Client, client_loop: asyncio.AbstractEventLoop
    ):
        self.topic_subscription_path = topic_subscription_path
        self.client = client
        self.client_loop = client_loop

        self.subscriber = pubsub_v1.SubscriberClient(credentials=credentials)
        self.stream = None

    def callback(self, message: pubsub_v1.subscriber.message.Message):
        message.ack()

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
    def __init__(self, topic_names: List[str]):
        self.listener_threads = {
            topic_subscription_path: GoogleTopicListenerThread(topic_subscription_path=topic_subscription_path)
            for topic_subscription_path in topic_names
        }

    @classmethod
    def init_and_run(cls, topic_names: List[str]):
        manager = cls(topic_names=topic_names)
        manager.start_listeners()
        return manager

    def start_listeners(self):
        for _, listener in self.listener_threads:
            listener.run()

    def add_subscription(self, topic_subscription_path: str):
        existing_thread = get_from_dict(self.listener_threads, [topic_subscription_path])

        if existing_thread:
            if not existing_thread.is_alive():
                del self.listener_threads[topic_subscription_path]
            return

        # Add subscription
        self.listener_threads[topic_subscription_path] = GoogleTopicListenerThread(topic_subscription_path=topic_subscription_path)
        self.listener_threads[topic_subscription_path].run()

    def close_stream(self, topic_subscription_path: str):
        stream = get_from_dict(self.listener_threads, topic_subscription_path)

        if stream:
            stream.close()
        else:
            raise Exception("No stream with the provided topic subscription path was found")

    def close_all_streams(self):
        for topic_subscription_path, listener_thread in self.listener_threads:
            if listener_thread.is_alive():
                listener_thread.close()
            else:
                logging.info(f"Listener for {topic_subscription_path} is already closed")
