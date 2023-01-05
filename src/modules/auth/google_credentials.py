import json
from typing import Literal, Optional

import discord
from google.auth import credentials
from google.oauth2 import credentials as oauth2_credentials
from google.oauth2 import service_account
from google_auth_oauthlib import flow
from ruamel.yaml import YAML

from src.cogs.google_forms.ui.views import AuthenticationLinkView
from src.utils.config import GoogleCredentialsConfig
from src.utils.helper import get_from_dict, send_or_edit_interaction_message

yaml = YAML(typ="safe")


class GoogleCredentialsHelper:
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

    SERVICE_ACCOUNT_CRED = None
    OAUTH2_CLIENT_ID_CRED = None

    @staticmethod
    def init_credentials():
        gc_conf = GoogleCredentialsConfig()

        oauth2_cred = (
            oauth2_credentials.Credentials(gc_conf.oauth2_client_id_credentials)
            if gc_conf.oauth2_client_id_credentials
            else None
        )
        service_acc_cred = (
            credentials.Credentials(gc_conf.service_account_credentials)
            if gc_conf.service_account_credentials
            else None
        )

        GoogleCredentialsHelper.OAUTH2_CLIENT_ID_CRED = (
            oauth2_credentials if oauth2_cred and oauth2_cred.valid else None
        )
        GoogleCredentialsHelper.SERVICE_ACCOUNT_CRED = (
            service_acc_cred if service_acc_cred and service_acc_cred.valid else None
        )

    @staticmethod
    def service_acc_cred():
        """This function will help set the account service credentials before returning the service account credentials"""
        GoogleCredentialsHelper.set_service_acc_cred(save_to_file=True)
        return GoogleCredentialsHelper.SERVICE_ACCOUNT_CRED

    @staticmethod
    def set_service_acc_cred(save_to_file: bool = False):
        if not GoogleCredentialsHelper.SERVICE_ACCOUNT_CRED or (
            GoogleCredentialsHelper.SERVICE_ACCOUNT_CRED and not GoogleCredentialsHelper.SERVICE_ACCOUNT_CRED.valid
        ):
            GoogleCredentialsHelper.SERVICE_ACCOUNT_CRED = service_account.Credentials.from_service_account_file(
                "service-account-info.json",
                scopes=GoogleCredentialsHelper.SERVICE_ACCOUNT_SCOPES,
                additional_claims={"audience": GoogleCredentialsHelper.SUBSCRIBER_AUDIENCE},
            )

            if save_to_file:
                GoogleCredentialsConfig().manage_credential(
                    type="service_account",
                    credential_dict=GoogleCredentialsHelper.credentials_to_dict(
                        credentials=GoogleCredentialsHelper.SERVICE_ACCOUNT_CRED
                    ),
                )

    @staticmethod
    def get_authorization_url():
        auth_flow = flow.Flow.from_client_secrets_file(
            "oauth2-client-id.json",
            scopes=GoogleCredentialsHelper.OAUTH2_CLIENT_ID_SCOPES,
            redirect_uri="urn:ietf:wg:oauth:2.0:oob",
        )
        auth_url, _ = auth_flow.authorization_url(
            access_type="offline", include_granted_scopes="true", prompt="consent"
        )
        return auth_url, auth_flow

    @staticmethod
    async def send_enter_auth_code_view(interaction: discord.Interaction, auth_url: str):
        auth_code_embed = discord.Embed(
            title="Enter Authentication Code",
            description='To authenticate your Google account:\n1️⃣ Click on the "Authenticate with Google" button\n2️⃣ Once you are redirected to the authentication portal, select an account and approve all permissions. Then, copy the authentication code.\n3️⃣ Click the "Enter Authentication Code" button and paste the authentication code.',
        )
        auth_code_embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.avatar)

        auth_link_view = AuthenticationLinkView(auth_url=auth_url, timeout=120)
        auth_message = await send_or_edit_interaction_message(
            interaction=interaction, embed=auth_code_embed, view=auth_link_view, ephemeral=True
        )

        return auth_message, auth_link_view

    @staticmethod
    def set_oauth2_client_id_token(auth_flow: flow.Flow, auth_code: str, save_to_file: bool = False):
        try:
            auth_flow.fetch_token(code=auth_code)
            GoogleCredentialsHelper.OAUTH2_CLIENT_ID_CRED = auth_flow.credentials

            if save_to_file:
                GoogleCredentialsConfig().manage_credential(
                    type="oauth2_client_id",
                    credential_dict=GoogleCredentialsHelper.credentials_to_dict(
                        credentials=GoogleCredentialsHelper.OAUTH2_CLIENT_ID_CRED
                    ),
                )

            return "Successfully logged in with Google account."
        except:
            return "Authentication code invalid."

    @staticmethod
    async def google_oauth_discord_flow(interaction: discord.Interaction):
        # 1. Get authorization URL
        auth_url, auth_flow = GoogleCredentialsHelper.get_authorization_url()

        # 2. Send Discord message and wait for user to enter the authentication code
        _, auth_link_view = await GoogleCredentialsHelper.send_enter_auth_code_view(
            interaction=interaction, auth_url=auth_url
        )

        # 3. Handle user inputted authentication code
        timeout = await auth_link_view.wait()
        if timeout or auth_link_view.is_cancelled:
            return await send_or_edit_interaction_message(
                interaction=interaction,
                edit_original_response=True,
                content="The command timed out, please try again!"
                if timeout
                else "Authentication process was cancelled.",
                view=None,
                embed=None,
                ephemeral=True,
            )

        token_response = GoogleCredentialsHelper.set_oauth2_client_id_token(
            auth_flow=auth_flow, auth_code=auth_link_view.auth_code, save_to_file=True
        )
        await send_or_edit_interaction_message(
            interaction=interaction,
            edit_original_response=True,
            content=token_response,
            view=None,
            embed=None,
            ephemeral=True,
        )

    @staticmethod
    def oauth_cred(interaction: Optional[discord.Interaction] = None, reset_cred: bool = False):
        if interaction and reset_cred:
            GoogleCredentialsHelper.set_oauth_cred(interaction=interaction)
        return GoogleCredentialsHelper.OAUTH2_CLIENT_ID_CRED

    @staticmethod
    async def set_oauth_cred(interaction: discord.Interaction, reset_cred: bool = False):
        if (
            not GoogleCredentialsHelper.OAUTH2_CLIENT_ID_CRED
            or (
                GoogleCredentialsHelper.OAUTH2_CLIENT_ID_CRED
                and not GoogleCredentialsHelper.OAUTH2_CLIENT_ID_CRED.valid
            )
            or reset_cred
        ):
            await GoogleCredentialsHelper.google_oauth_discord_flow(interaction=interaction)

        if not GoogleCredentialsHelper.OAUTH2_CLIENT_ID_CRED:
            raise Exception("Authentication via Discord has failed.")

    @staticmethod
    def credentials_to_dict(credentials: oauth2_credentials.Credentials | service_account.Credentials):
        return (
            json.loads(credentials.to_json())
            if isinstance(credentials, oauth2_credentials.Credentials)
            else {"token": credentials.token, "scopes": credentials.scopes}
        )
