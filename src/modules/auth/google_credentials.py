import discord
from google.oauth2 import service_account
from google_auth_oauthlib import flow
from ruamel.yaml import YAML

from src.cogs.google_forms.ui.views import AuthenticationLinkView
from src.utils.helper import send_or_edit_interaction_message

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

    @staticmethod
    def service_acc_cred():
        """This function will help set the account service credentials before returning the service account credentials"""
        GoogleCredentialsHelper.set_service_acc_cred()
        return GoogleCredentialsHelper.SERVICE_ACCOUNT_CRED

    @staticmethod
    def set_service_acc_cred():
        if not GoogleCredentialsHelper.SERVICE_ACCOUNT_CRED or (
            GoogleCredentialsHelper.SERVICE_ACCOUNT_CRED and not GoogleCredentialsHelper.SERVICE_ACCOUNT_CRED.valid
        ):
            GoogleCredentialsHelper.SERVICE_ACCOUNT_CRED = service_account.Credentials.from_service_account_file(
                "service-account-info.json",
                scopes=GoogleCredentialsHelper.SERVICE_ACCOUNT_SCOPES,
                additional_claims={"audience": GoogleCredentialsHelper.SUBSCRIBER_AUDIENCE},
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

        # 4. Fetch token and return credentials
        try:
            auth_flow.fetch_token(code=auth_link_view.auth_code)

            await send_or_edit_interaction_message(
                interaction=interaction,
                edit_original_response=True,
                content="Successfully logged in with Google account.",
                view=None,
                embed=None,
                ephemeral=True,
            )

            return auth_flow.credentials
        except:
            await send_or_edit_interaction_message(
                interaction=interaction,
                edit_original_response=True,
                content="Authentication code invalid.",
                view=None,
                embed=None,
                ephemeral=True,
            )

            return None
