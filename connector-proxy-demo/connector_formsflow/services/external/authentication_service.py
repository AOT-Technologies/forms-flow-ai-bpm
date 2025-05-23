import base64
from contextlib import contextmanager
import enum
import json
from typing import Any, NotRequired, TypedDict, cast

import jwt
import requests
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509 import load_der_x509_certificate
from security import safe_requests  # type: ignore
from flask import current_app


HTTP_REQUEST_TIMEOUT_SECONDS = 15
SPIFF_OPEN_ID_KEY_ID = "spiffworkflow_backend_open_id"
SPIFF_OPEN_ID_ALGORITHM = "RS256"


class AuthenticationProviderTypes(enum.Enum):
    open_id = "open_id"
    internal = "internal"


class AuthenticationOptionForApi(TypedDict):
    identifier: str
    label: str
    uri: str
    additional_valid_client_ids: NotRequired[str]


class AuthenticationOption(AuthenticationOptionForApi):
    client_id: str
    client_secret: str


class AuthenticationOptionNotFoundError(Exception):
    pass


class AuthenticationService:
    """This class manages all the Keycloak service API calls."""

    ENDPOINT_CACHE: dict[str, dict[str, str]] = (
        {}
    )  # We only need to find the openid endpoints once, then we can cache them.
    JSON_WEB_KEYSET_CACHE: dict[str, dict[str, str]] = {}

    def __init__(self, session):
        """Initializing the service."""
        self.session = session
        bpm_token_api = current_app.config.get("BPM_TOKEN_API")
        bpm_client_id = current_app.config.get("BPM_CLIENT_ID")
        bpm_client_secret = current_app.config.get("BPM_CLIENT_SECRET")
        bpm_grant_type = current_app.config.get("BPM_GRANT_TYPE", "open")
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        payload = {
            "client_id": bpm_client_id,
            "client_secret": bpm_client_secret,
            "grant_type": bpm_grant_type,
        }

        response = requests.post(
            bpm_token_api, headers=headers, data=payload, timeout=30
        )
        data = json.loads(response.text)
        assert data["access_token"] is not None
        self.session.headers.update(
            {
                "Authorization": "Bearer " + data["access_token"],
                "Content-Type": "application/json",
            }
        )

    @classmethod
    def jwks_public_key_for_key_id(
        cls, authentication_identifier: str, key_id: str
    ) -> dict:
        jwks_uri = cls.open_id_endpoint_for_name("jwks_uri", authentication_identifier)
        jwks_configs = cls.get_jwks_config_from_uri(jwks_uri)
        json_key_configs: dict = next(
            jk for jk in jwks_configs["keys"] if jk["kid"] == key_id
        )
        return json_key_configs

    @classmethod
    def get_jwks_config_from_uri(cls, jwks_uri: str) -> dict:
        if jwks_uri not in AuthenticationService.JSON_WEB_KEYSET_CACHE:
            try:
                jwt_ks_response = safe_requests.get(
                    jwks_uri, timeout=HTTP_REQUEST_TIMEOUT_SECONDS
                )
                AuthenticationService.JSON_WEB_KEYSET_CACHE[jwks_uri] = (
                    jwt_ks_response.json()
                )
            except requests.exceptions.ConnectionError as ce:
                raise Exception(f"Cannot connect to given jwks url: {jwks_uri}") from ce
        return AuthenticationService.JSON_WEB_KEYSET_CACHE[jwks_uri]

    @classmethod
    def server_url(cls, authentication_identifier: str) -> str:
        """Returns the server url from the config."""
        config: str = cls.authentication_option_for_identifier(
            authentication_identifier
        )["uri"]
        return config

    @classmethod
    def authentication_option_for_identifier(
        cls, authentication_identifier: str
    ) -> AuthenticationOption:
        for config in current_app.config["SPIFFWORKFLOW_BACKEND_AUTH_CONFIGS"]:
            if config["identifier"] == authentication_identifier:
                return_config: AuthenticationOption = config
                return return_config
        raise AuthenticationOptionNotFoundError(
            f"Could not find a config with identifier '{authentication_identifier}'"
        )

    @classmethod
    def client_id(cls, authentication_identifier: str) -> str:
        """Returns the client id from the config."""
        config: str = cls.authentication_option_for_identifier(
            authentication_identifier
        )["client_id"]
        return config

    @classmethod
    def valid_audiences(cls, authentication_identifier: str) -> list[str]:
        return [cls.client_id(authentication_identifier), "account"]

    @classmethod
    def open_id_endpoint_for_name(
        cls, name: str, authentication_identifier: str
    ) -> str:
        """All openid systems provide a mapping of static names to the full path of that endpoint."""
        appropriate_server_url = cls.server_url(authentication_identifier)
        openid_config_url = f"{appropriate_server_url}/.well-known/openid-configuration"

        if authentication_identifier not in cls.ENDPOINT_CACHE:
            cls.ENDPOINT_CACHE[authentication_identifier] = {}
        if authentication_identifier not in cls.JSON_WEB_KEYSET_CACHE:
            cls.JSON_WEB_KEYSET_CACHE[authentication_identifier] = {}
        if name not in AuthenticationService.ENDPOINT_CACHE[authentication_identifier]:
            try:
                response = safe_requests.get(
                    openid_config_url, timeout=HTTP_REQUEST_TIMEOUT_SECONDS
                )
                AuthenticationService.ENDPOINT_CACHE[authentication_identifier] = (
                    response.json()
                )
            except requests.exceptions.ConnectionError as ce:
                raise Exception(
                    f"Cannot connect to given open id url: {openid_config_url}"
                ) from ce
        if name not in AuthenticationService.ENDPOINT_CACHE[authentication_identifier]:
            raise Exception(
                f"Unknown OpenID Endpoint: {name}. Tried to get from {openid_config_url}"
            )
        config: str = AuthenticationService.ENDPOINT_CACHE[
            authentication_identifier
        ].get(name, "")
        return config

    @classmethod
    def public_key_from_rsa_public_numbers(cls, json_key_configs: dict) -> Any:
        modulus = base64.urlsafe_b64decode(json_key_configs["n"] + "===")
        exponent = base64.urlsafe_b64decode(json_key_configs["e"] + "===")
        public_key_numbers = rsa.RSAPublicNumbers(
            int.from_bytes(exponent, byteorder="big"),
            int.from_bytes(modulus, byteorder="big"),
        )
        return public_key_numbers.public_key(backend=default_backend())

    @classmethod
    def public_key_from_x5c(cls, key_id: str, json_key_configs: dict) -> Any:
        x5c = json_key_configs["x5c"][0]
        decoded_certificate = base64.b64decode(x5c)

        # our backend-based openid provider implementation (which you should never use in prod)
        # uses a public/private key pair. we played around with adding an x509 cert so we could
        # follow the exact same mechanism for getting the public key that we use for keycloak,
        # but using an x509 cert for no reason seemed a little overboard for this toy-openid use case,
        # when we already have the public key that can work hardcoded in our config.
        if key_id == SPIFF_OPEN_ID_KEY_ID:
            return decoded_certificate
        else:
            x509_cert = load_der_x509_certificate(
                decoded_certificate, default_backend()
            )
            return x509_cert.public_key()

    @classmethod
    def parse_jwt_token(cls, authentication_identifier: str, token: str) -> dict:
        header = jwt.get_unverified_header(token)
        key_id = str(header.get("kid"))
        parsed_token: dict | None = None

        algorithm = str(header.get("alg"))
        json_key_configs = cls.jwks_public_key_for_key_id(
            authentication_identifier, key_id
        )
        public_key: Any = None
        jwt_decode_options = {
            "verify_exp": False,
            "verify_aud": False,
            "verify_iat": current_app.config[
                "SPIFFWORKFLOW_BACKEND_OPEN_ID_VERIFY_IAT"
            ],
            "verify_nbf": current_app.config[
                "SPIFFWORKFLOW_BACKEND_OPEN_ID_VERIFY_NBF"
            ],
            "leeway": current_app.config["SPIFFWORKFLOW_BACKEND_OPEN_ID_LEEWAY"],
        }

        if "x5c" not in json_key_configs:
            public_key = cls.public_key_from_rsa_public_numbers(json_key_configs)
        else:
            public_key = cls.public_key_from_x5c(key_id, json_key_configs)

        # tokens generated from the cli have an aud like: [ "realm-management", "account" ]
        # while tokens generated from frontend have an aud like: "spiffworkflow-backend."
        # as such, we cannot simply pull the first valid audience out of cls.valid_audiences(authentication_identifier)
        # and then shove it into decode (it will raise), but we need the algorithm from validate_decoded_token that checks
        # if the audience in the token matches any of the valid audience values. Therefore do not check aud here.
        parsed_token = jwt.decode(
            token,
            public_key,
            algorithms=[algorithm],
            audience=cls.valid_audiences(authentication_identifier)[0],
            options=jwt_decode_options,
        )
        return cast(dict, parsed_token)

    @classmethod
    def get_bpm_client_token(cls) -> str:
        """Authorizes with Keycloak using BPM clientId and secret and returns the token

        Returns:
            JWT Token
        """
        bpm_token_api = current_app.config.get("BPM_TOKEN_API")
        bpm_client_id = current_app.config.get("BPM_CLIENT_ID")
        bpm_client_secret = current_app.config.get("BPM_CLIENT_SECRET")
        bpm_grant_type = current_app.config.get("BPM_GRANT_TYPE", "open")
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        payload = {
            "client_id": bpm_client_id,
            "client_secret": bpm_client_secret,
            "grant_type": bpm_grant_type,
        }

        response = requests.post(
            bpm_token_api, headers=headers, data=payload, timeout=30
        )
        data = json.loads(response.text)
        assert data["access_token"] is not None
        return data["access_token"]


@contextmanager
def session_with_auth(token: str | None = None, token_header_key: str = "Authorization") -> requests.Session:  # type: ignore
    """Creates and returns a session with authorization headers

    Keyword Arguments:
        token {str | None} -- Auth token (default: {None})

    Returns:
        requests.Session -- session with auth headers
    """
    try:
        session = requests.Session()
        if token_header_key == "Authorization":
            if token:
                # TODO: Change hardcoded "default"
                # TODO: Handle token expiry
                decoded_token = AuthenticationService.parse_jwt_token("default", token)
                config = AuthenticationService.ENDPOINT_CACHE["default"]
                pass

            else:
                token = AuthenticationService.get_bpm_client_token()
            token = f"Bearer {token}"
        headers = {"Content-Type": "application/json", f"{token_header_key}": token}
        session.headers.update(headers)
        yield session
    except Exception as e:
        current_app.logger.debug(f"Exception in session context. {e}")
    finally:
        session.close()
