from contextlib import contextmanager
from http import HTTPStatus
from typing import Dict
from flask import current_app
import requests

from connector_formsflow.services.external.authentication_service import (
    AuthenticationService,
    session_with_auth,
)
from connector_formsflow.services.utils.type_defs import (
    ApplicationAuditPayload,
    ApplicationStatePayload,
)


class WebAPIService:
    """Implements web api calls"""

    web_api_url = current_app.config.get("FF_WEB_API_URL")
    session = None

    @classmethod
    def update_application_state(
        cls, application_id: int, payload: ApplicationStatePayload
    ):
        """Calls the application state API

        Arguments:
            payload {dict} -- Payload to the API
        """
        url = f"{cls.web_api_url}/application/{application_id}"
        with session_with_auth() as session:
            response = session.put(url, json=payload)
            return response.json(), response.status_code

    @classmethod
    def create_application_audit(
        cls, application_id: int, payload: ApplicationAuditPayload
    ):
        """Calls the application audit API

        Arguments:
            application_id {int} -- ID of the application to update
            payload {ApplicationAuditPayload} -- payload to the API
        """
        url = f"{cls.web_api_url}/application/{application_id}/history"
        with session_with_auth() as session:
            response = session.post(url, json=payload)
            return response.json(), response.status_code

    @classmethod
    def fetch_application_details(cls, application_id: int) -> Dict:
        """Fetches the application details from web API for given application id

        Arguments:
            application_id {int}

        Returns:
            Dict
        """

        url = f"{cls.web_api_url}/form/applicationid/{application_id}"
        with session_with_auth() as session:
            application_response = session.get(url)
            if application_response.status_code != HTTPStatus.OK:
                raise Exception(
                    f"Failed to fetch application details. API response: {application_response.json()}"
                )
            return application_response.json()
