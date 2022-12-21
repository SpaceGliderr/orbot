import asyncio
from typing import Literal, Optional

import discord
from google.auth import credentials
from google.oauth2 import credentials as oauth2_credentials
from google.oauth2 import service_account
from google_auth_oauthlib import flow
from ruamel.yaml import YAML

from src.cogs.google_forms.ui.views import AuthenticationLinkView
from src.utils.helper import get_from_dict
from src.utils.user_input import get_user_input

yaml = YAML(typ="safe")


class GoogleCredentials:
    SERVICE_ACCOUNT_SCOPES = [
        "https://www.googleapis.com/auth/forms.body",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/cloud-platform",
        "https://www.googleapis.com/auth/pubsub",
    ]
    OAUTH2_CLIENT_ID_SCOPES = [
        "https://www.googleapis.com/auth/forms.body",
        "https://www.googleapis.com/auth/cloud-platform",
        "https://www.googleapis.com/auth/pubsub",
    ]
    SUBSCRIBER_AUDIENCE = "https://pubsub.googleapis.com/google.pubsub.v1.Subscriber"
    PUBLISHER_AUDIENCE = "https://pubsub.googleapis.com/google.pubsub.v1.Publisher"

    SERVICE_ACCOUNT_CRED = None
    OAUTH2_CLIENT_ID_CRED = None

    @staticmethod
    def get_service_acc_cred():
        GoogleCredentials.set_service_account_cred()
        return GoogleCredentials.SERVICE_ACCOUNT_CRED

    @staticmethod
    async def send_input_message(interaction: discord.Interaction, auth_url: str):
        user_input_embed = discord.Embed(
            title="Enter authentication code",
            description=f"The next message you send in <#{interaction.channel_id}> will be recorded as the authentication code",
        )
        user_input_embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.avatar)

        link_view = AuthenticationLinkView(auth_url=auth_url, timeout=60)

        if not interaction.response.is_done():
            await interaction.response.send_message(embed=user_input_embed, view=link_view)
            message = await interaction.original_response()
        else:
            message = await interaction.followup.send(embed=user_input_embed, view=link_view)

        return message, link_view

    @staticmethod
    async def google_oauth_process(bot: discord.Client, interaction: discord.Interaction):
        if GoogleCredentials.OAUTH2_CLIENT_ID_CRED:
            return GoogleCredentials.OAUTH2_CLIENT_ID_CRED

        # 1. Get authorization URL
        auth_url, auth_flow = GoogleCredentials.get_authorization_url()

        # 2. Send user input message
        input_message, link_view = await GoogleCredentials.send_input_message(
            interaction=interaction, auth_url=auth_url
        )

        # 3. Get user input of the Authentication Code
        timeout = await link_view.wait()

        if timeout or link_view.is_cancelled:
            await asyncio.gather(
                input_message.delete(),
                interaction.followup.send(
                    content="The command timed out, please try again!"
                    if timeout
                    else "Authentication process cancelled.",
                    ephemeral=True,
                ),
            )
        else:
            await input_message.delete()

            result = GoogleCredentials.set_oauth2_client_id_token(
                auth_flow=auth_flow, auth_code=link_view.auth_code, save_to_file=True
            )
            await interaction.followup.send(content=result, ephemeral=True)

    @staticmethod
    async def get_oauth_cred(
        on_discord: bool = False,
        bot: Optional[discord.Client] = None,
        interaction: Optional[discord.Interaction] = None,
    ):
        if on_discord and not bot and not interaction:
            raise Exception("Need to pass in bot and interaction arguments.")
        if not GoogleCredentials.OAUTH2_CLIENT_ID_CRED and on_discord:
            await GoogleCredentials.google_oauth_process(bot=bot, interaction=interaction)

            if not GoogleCredentials.OAUTH2_CLIENT_ID_CRED:
                raise Exception("Authentication via Discord has failed.")
        return GoogleCredentials.OAUTH2_CLIENT_ID_CRED

    @staticmethod
    def init_credentials():
        with open("src/data/google_credentials.yaml", "r") as google_cred_file:
            data = yaml.load(google_cred_file)

            if data:
                oauth2_cred = data.get("oauth2_client_id_credentials", None)
                GoogleCredentials.OAUTH2_CLIENT_ID_CRED = GoogleCredentials.load_credentials_dict(oauth2_cred, "oauth2")

                # service_acc_cred = data.get("service_account_credentials", None)
                # GoogleCredentials.SERVICE_ACCOUNT_CRED = GoogleCredentials.load_credentials_dict(
                #     service_acc_cred, "service_acc"
                # )

    @staticmethod
    def load_credentials_dict(credentials_dict: dict | None, cred_type: Literal["oauth2", "service_acc"]):
        if not credentials_dict:
            return None
        try:
            if cred_type == "oauth2":
                return oauth2_credentials.Credentials(**credentials_dict)
            elif cred_type == "service_acc":
                return credentials.Credentials(**credentials_dict)
            return None
        except:
            return None

    @staticmethod
    def set_service_account_cred():
        if not GoogleCredentials.SERVICE_ACCOUNT_CRED or (
            GoogleCredentials.SERVICE_ACCOUNT_CRED and not GoogleCredentials.SERVICE_ACCOUNT_CRED.valid
        ):
            GoogleCredentials.SERVICE_ACCOUNT_CRED = service_account.Credentials.from_service_account_file(
                "service-account-info.json",
                scopes=GoogleCredentials.SERVICE_ACCOUNT_SCOPES,
                additional_claims={"audience": GoogleCredentials.SUBSCRIBER_AUDIENCE},
            )

    @staticmethod
    def get_authorization_url():
        auth_flow = flow.Flow.from_client_secrets_file(
            "oauth2-client-id.json",
            scopes=GoogleCredentials.OAUTH2_CLIENT_ID_SCOPES,
            redirect_uri="urn:ietf:wg:oauth:2.0:oob",
        )
        authorization_url, _ = auth_flow.authorization_url(
            access_type="offline", include_granted_scopes="true", prompt="consent"
        )
        return authorization_url, auth_flow

    @staticmethod
    def set_oauth2_client_id_token(auth_flow: flow.Flow, auth_code: str, save_to_file: bool = False):
        try:
            print("AUTH CODE >>> ", auth_code)
            auth_flow.fetch_token(code=auth_code)
            print("AUTH FLOW >>> ", auth_flow.credentials.refresh_token)
            GoogleCredentials.OAUTH2_CLIENT_ID_CRED = auth_flow.credentials
            print("AUTHENTICATION COMPLETE")

            if save_to_file:
                print("SAVING TO FILE...")
                GoogleCredentials.save_credentials_to_file()
                print("FILE SAVED")

            return "Successfully logged in with Google account."
        except Exception as e:
            print("ERROR >>> ", e)
            return "Authentication code invalid."

    @staticmethod
    def save_credentials_to_file():
        with open("src/data/google_credentials.yaml", "w") as google_cred_file:
            data = {}

            if GoogleCredentials.OAUTH2_CLIENT_ID_CRED:
                data["oauth2_client_id_credentials"] = GoogleCredentials.credentials_to_dict(
                    GoogleCredentials.OAUTH2_CLIENT_ID_CRED
                )

            if GoogleCredentials.SERVICE_ACCOUNT_CRED:
                print("SERVICE ACCOUNT", GoogleCredentials.SERVICE_ACCOUNT_CRED)
                data["service_account_credentials"] = GoogleCredentials.credentials_to_dict(
                    GoogleCredentials.SERVICE_ACCOUNT_CRED
                )

            yaml.dump(data, google_cred_file)

    @staticmethod
    def delete_credential_from_file(type: Literal["service_account, oauth2_client_id"]):
        with open("src/data/google_credentials.yaml", "r") as google_cred_file:
            data = yaml.load(google_cred_file)

        cred_type = f"{type}_credentials"
        cred = get_from_dict(data, [cred_type])
        if cred:
            data[cred_type] = None

        with open("src/data/google_credentials.yaml", "w") as google_cred_file:
            yaml.dump(data, google_cred_file)

    @staticmethod
    def credentials_to_dict(credentials: oauth2_credentials.Credentials | service_account.Credentials):
        data = {
            "token": credentials.token,
            "scopes": credentials.scopes,
        }

        if isinstance(credentials, oauth2_credentials.Credentials):
            data = {
                **data,
                "token_uri": credentials.token_uri,
                "refresh_token": credentials.refresh_token,
                "client_id": credentials.client_id,
                "client_secret": credentials.client_secret,
            }

        print("DATA >>> ", data)

        return data
