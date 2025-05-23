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

    # @classmethod
    # def init(cls):
    #     """Initialize a requests session and authenticates it with Keycloak"""
    #     session = requests.Session()
    #     AuthenticationService(session)
    #     cls.session = session

    # @classmethod
    # def _get_token_info(cls) -> Dict:
    #     """Decode and return the token info from headers"""
    #     try:
    #         token = request.headers["Authorization"].removeprefix("Bearer ")
    #     except KeyError:
    #         return None
    #     if token:
    #         # TODO: Change hardcoded "default"
    #         decoded_token = AuthenticationService.parse_jwt_token("default", token)
    #         return decoded_token
    #     return None

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
            print(response)
            print(response.json())
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
            print(response)
            print(response.json())
            return response.json(), response.status_code

    # @classmethod
    # def _get_submitted_by(cls, task_data: Dict) -> str:
    #     """Return submitted by username

    #     Arguments:
    #         task_data {Dict} -- the task data available to the workflow

    #     Returns:
    #         str -- submitted by username
    #     """
    #     decoded_token = cls._get_token_info()
    #     if decoded_token:
    #         submitted_by = decoded_token["preferred_username"]
    #         if submitted_by.startswith("service-account"):
    #             submitted_by = "Anonymous-User"
    #     else:
    #         submitted_by = task_data["data"].get("currentUser", None)
    #     return submitted_by

    # @classmethod
    # def _prepare_application_state_payload(cls, task_data: Dict) -> Dict:
    #     """Prepare the web api payload from task data

    #     Arguments:
    #         task_data {Dict} -- The task data available to the workflow

    #     Returns:
    #         Dict -- Payload for web API
    #     """
    #     submitted_by = cls._get_submitted_by(task_data)
    #     payload = {
    #         "applicationStatus": task_data["status"],
    #         "formUrl": task_data["data"].get("formUrl"),
    #         "isResubmit": bool(task_data["data"].get("isResubmit", None)),
    #         "eventName": task_data["data"].get("eventName", None),
    #         "submittedBy": submitted_by,
    #     }
    #     return payload

    # @classmethod
    # def _prepare_application_audit_payload(cls, task_data: Dict) -> Dict:
    #     """Prepare the web api payload from task data

    #     Arguments:
    #         task_data {Dict} -- The task data available to the workflow

    #     Returns:
    #         Dict -- Payload for web API
    #     """
    #     submitted_by = cls._get_submitted_by(task_data)
    #     payload = {
    #         "applicationStatus": task_data["status"],
    #         "formUrl": task_data["data"].get("formUrl"),
    #         "color": task_data["data"].get("color", None),
    #         "submittedBy": submitted_by,
    #         "percentage": task_data["data"].get("percentage", None),
    #     }
    #     return payload

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
            print(application_response.json())
            return application_response.json()
