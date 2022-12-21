import asyncio
import os
import threading
from typing import List, Optional, Union

import discord
from apiclient import discovery
from google.cloud import pubsub_v1
from googleapiclient.errors import HttpError

from src.modules.auth.google_credentials import GoogleCredentials
from src.modules.google_forms.service import GoogleFormsService
from src.modules.ui.custom import PaginatedEmbedsView
from src.utils.config import GoogleCloudConfig
from src.utils.helper import get_from_dict


class GoogleFormsResponseListener:
    def __init__(self, client: discord.Client, client_loop: asyncio.AbstractEventLoop) -> None:
        self.subscriber = pubsub_v1.SubscriberClient(credentials=GoogleCredentials.get_service_acc_cred())
        self.service = GoogleFormsService.init_service_acc()
        self.client = client
        self.client_loop = client_loop

    def listen_in_thread(self):
        """A non-blocking call"""
        thread = threading.Thread(target=self.listen)
        # thread.daemon = True
        thread.start()

    def listen(self):
        """A blocking call"""
        stream = self.subscriber.subscribe(
            subscription=os.getenv("DEFAULT_FORMS_SUBSCRIPTION_PATH"), callback=self.stream_callback
        )

        print("STARTED LISTENING")
        with self.subscriber:
            try:
                print("LISTENING...")
                stream.result()
            except (TimeoutError, KeyboardInterrupt) as err:
                print(err)
                stream.cancel()
                stream.result()

        print("CLOSED")

    def stream_callback(self, message: pubsub_v1.subscriber.message.Message):
        message.ack()
        print("ACKNOWLEDGED")
        print("MESSAGE >>> ", message)
        schema = GoogleCloudConfig().active_form_schemas[message.attributes["formId"]]
        latest_response = self.service.get_latest_response(message.attributes["formId"], schema["linked_sheet_id"])
        idx, watch = GoogleCloudConfig().search_active_form_watch(
            form_id=message.attributes["formId"], watch_id=message.attributes["watchId"]
        )
        print("LATEST RESPONSE >>> ", latest_response)
        print("WATCH >>> ", watch)

        asyncio.run_coroutine_threadsafe(
            self.broadcast_to_channel(
                channel_id=watch["broadcast_channel_id"],
                form_response=latest_response,
                form_id=message.attributes["formId"],
            ),
            self.client_loop,
        )

    async def broadcast_to_channel(self, channel_id: str, form_response: Union[dict, List[dict]], form_id: str):
        channel = await self.client.fetch_channel(int(channel_id))
        print("CHANNEL >>> ", channel.__class__)
        responses = form_response["answers"] if isinstance(form_response, dict) else form_response
        print("RESPONSES PARAMS >>> ", responses)
        embeds = GoogleCloudConfig().generate_response_embeds(responses=responses, form_id=form_id)
        view = PaginatedEmbedsView(embeds=embeds) if len(embeds) > 1 else None
        asyncio.run_coroutine_threadsafe(channel.send(embed=embeds[0], view=view), self.client_loop)
        print("SENT")
