import discord
from google.oauth2 import service_account
from google_auth_oauthlib import flow
from ruamel.yaml import YAML

from src.cogs.google_forms.ui.view import AuthenticationLinkView
from src.utils.helper import send_or_edit_interaction_message

yaml = YAML(typ="safe")


class GoogleCredentialsHelper:
    """A class comprised of static resources to handle authentication using the Google APIs."""

    # =================================================================================================================
    # STATIC VARIABLES
    # =================================================================================================================
    CREDENTIAL_SCOPES = [
        "https://www.googleapis.com/auth/forms.body",  # Used for accessing the Google Form
        "https://www.googleapis.com/auth/drive",  # Used for accessing Google Sheets of the responses
        "https://www.googleapis.com/auth/cloud-platform",  # Used for GCP and PubSub features
        "https://www.googleapis.com/auth/pubsub",
    ]
    SUBSCRIBER_AUDIENCE = "https://pubsub.googleapis.com/google.pubsub.v1.Subscriber"  # Subscriber audience required for service account to subscribe to topic
    SERVICE_ACCOUNT_CRED = None  # Store a static variable of the service account credential object for easy access

    # =================================================================================================================
    # SERVICE ACCOUNT CREDENTIALS
    # =================================================================================================================
    @staticmethod
    def service_acc_cred():
        """A static method that helps set the account service credentials and returns the service account credentials."""
        GoogleCredentialsHelper.set_service_acc_cred()
        return GoogleCredentialsHelper.SERVICE_ACCOUNT_CRED

    @staticmethod
    def set_service_acc_cred():
        """A static method that sets the account service credentials."""
        if not GoogleCredentialsHelper.SERVICE_ACCOUNT_CRED or (
            GoogleCredentialsHelper.SERVICE_ACCOUNT_CRED and not GoogleCredentialsHelper.SERVICE_ACCOUNT_CRED.valid
        ):  # Check whether the static variable for the service account credential exists or not
            GoogleCredentialsHelper.SERVICE_ACCOUNT_CRED = service_account.Credentials.from_service_account_file(
                "service-account-info.json",
                scopes=GoogleCredentialsHelper.CREDENTIAL_SCOPES,
                additional_claims={"audience": GoogleCredentialsHelper.SUBSCRIBER_AUDIENCE},
            )

    # =================================================================================================================
    # GOOGLE AUTHORIZATION FLOW
    # =================================================================================================================
    # Obtain the Google authentication flow
    # - The authentication flow is a sequence of actions that will allow a user to generate an auth token using their Google account
    # - Authentication flow:
    #   (1) Generate authentication URL and Flow object
    #   (2) Redirect user to the authentication URL
    #   (3) User logs in and approves permissions (in external browser)
    #   (4) Authentication code is generated
    #   (5) User enters authentication code in a Discord modal
    #   (6) Authentication token is generated and given to the Flow object
    #   (7) A valid OAuth Credential is generated and can be used
    @staticmethod
    def get_authorization_url():
        """A static method that obtains the authorization URL to authenticate a Google account. Obtains Step (1) and (2) of the authentication flow."""
        auth_flow = flow.Flow.from_client_secrets_file(
            "oauth2-client-id.json",
            scopes=GoogleCredentialsHelper.CREDENTIAL_SCOPES,
            redirect_uri="urn:ietf:wg:oauth:2.0:oob",
        )
        auth_url, _ = auth_flow.authorization_url(
            access_type="offline", include_granted_scopes="true", prompt="consent"
        )
        return auth_url, auth_flow

    @staticmethod
    async def send_enter_auth_code_view(interaction: discord.Interaction, auth_url: str):
        """A static method that sends a `AuthenticationLinkView` which will obtain the generated authentication code from Step (4) of the authentication flow through a modal.
        It is the start of Step (5) in the authentication flow.

        Parameters
        ----------
            * interaction: :class:`discord.Interaction`
            * auth_url: :class:`str`
                - The authentication URL that the user will be redirected to.
        """
        auth_code_embed = discord.Embed(
            title="Enter Authentication Code",
            description='To authenticate your Google account:\n1️⃣ Click on the "Authenticate with Google" button\n2️⃣ Once you are redirected to the authentication portal, select an account and approve all permissions. Then, copy the authentication code.\n3️⃣ Click the "Enter Authentication Code" button and paste the authentication code.',
        )
        auth_code_embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.avatar)

        auth_link_view = AuthenticationLinkView(auth_url=auth_url, timeout=120)  # Send authentication code modal

        auth_message = await send_or_edit_interaction_message(
            interaction=interaction, embed=auth_code_embed, view=auth_link_view, ephemeral=True
        )

        return auth_message, auth_link_view

    @staticmethod
    async def google_oauth_discord_flow(interaction: discord.Interaction):
        """A static method that gets the OAuth Google Account Credentials via Discord.

        Authentication Flow
        ----------
        1. Generate authentication URL and Flow object
        2. Redirect user to the authentication URL
        3. User logs in and approves permissions (in external browser)
        4. Authentication code is generated
        5. User enters authentication code in a Discord modal
        6. Authentication token is generated and given to the Flow object
        7. A valid OAuth Credential is generated and can be used

        Parameters
        ----------
            * interaction: :class:`discord.Interaction`
                - To send the messages to Discord.
        """
        # Step 1
        auth_url, auth_flow = GoogleCredentialsHelper.get_authorization_url()

        # Step 2, 3, and 4
        _, auth_link_view = await GoogleCredentialsHelper.send_enter_auth_code_view(
            interaction=interaction, auth_url=auth_url
        )

        # Step 5
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

        # Step 6 and 7
        try:  # If anything goes wrong when fetching the token from the Flow object
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
