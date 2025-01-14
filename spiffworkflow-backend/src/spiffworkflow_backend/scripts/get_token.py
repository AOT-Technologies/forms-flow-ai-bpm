import requests
from flask import current_app


def create_token() -> str:
    """Create keycloak service token and return."""
    # Get Keycloak configuration from Flask app config
    url: str = current_app.config.get("SPIFFWORKFLOW_BACKEND_AUTH_CONFIGS").get("uri")
    client: str = current_app.config.get("SPIFFWORKFLOW_BACKEND_AUTH_CONFIGS").get("client_id")
    secret: str = current_app.config.get("SPIFFWORKFLOW_BACKEND_AUTH_CONFIGS").get("client_secret")

    # Prepare the token request payload
    token_url = f"{url}/protocol/openid-connect/token"
    data = {
        'grant_type': 'client_credentials',
        'client_id': client,
        'client_secret': secret
    }

    # Make the request to Keycloak to get the token
    try:
        response = requests.post(token_url, data=data)
        response.raise_for_status()  # Raise an error for bad status codes

        # Parse the access token from the response
        token_data = response.json()
        return token_data.get('access_token')

    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"Failed to retrieve token: {e}")
        raise