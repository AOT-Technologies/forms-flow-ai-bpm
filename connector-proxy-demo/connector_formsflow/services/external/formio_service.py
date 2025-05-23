from http import HTTPStatus
import json
from typing import Dict, List
from flask import current_app
import requests

from connector_formsflow.services.external.authentication_service import (
    session_with_auth,
)
from connector_formsflow.services.utils.helpers import substring_before_last
from connector_formsflow.services.utils.type_defs import PatchSubmissionItem


class FormIOService:
    """Implements FormIO API calls"""

    session = None
    form_io_token = None
    base_url = current_app.config.get("FORMIO_URL")

    def __init__(self):
        self.base_url = current_app.config.get("FORMIO_URL")

    def patch_form_attributes(self, form_url: str, payload: List[PatchSubmissionItem]):
        """Patch task data attributes to FormIO

        Arguments:
            form_url  {str} -- The submission form URL
            payload {List[Dict]} -- Payload to patch submission FormIO API
        """
        formio_token = self.generate_formio_token()
        with session_with_auth(
            token=formio_token, token_header_key="x-jwt-token"
        ) as session:
            response = session.patch(form_url, json=payload)
            print(response)
            print(response.json())
            return response.json(), response.status_code

    def generate_formio_token(self):
        """Method to generate formio token using formio login API."""
        headers = {"Content-Type": "application/json"}
        url = f"{self.base_url}/user/login"
        payload = {
            "data": {
                "email": current_app.config.get("FORMIO_USERNAME"),
                "password": current_app.config.get("FORMIO_PASSWORD"),
            }
        }
        current_app.logger.info("Generate formio token using formio login API.")
        try:
            response = requests.post(url, headers=headers, data=json.dumps(payload))
            if response.ok:
                form_io_token = response.headers["x-jwt-token"]
                return form_io_token
            else:
                raise Exception(f"Failed to authenticate FormIO. {response.json()}")
        except requests.ConnectionError:
            raise Exception("Form service is not available")

    def fetch_submission(self, form_url: str):
        """Fetch submission data from FormIO

        Arguments:
            form_url {str} -- The submission form URL
        """
        formio_token = self.generate_formio_token()
        with session_with_auth(
            token=formio_token, token_header_key="x-jwt-token"
        ) as session:
            response = session.get(form_url)
            print(response)
            if response.status_code != HTTPStatus.OK:
                raise Exception(
                    f"Failed to fetch submission. API response: {response.json()}"
                )
            print(response.json())
            return response.json()

    def create_revision(self, form_url: str, submission: Dict) -> str:
        """Creates a new submission entry in FormIO and returns the ID

        Arguments:
            form_url {str} -- The submission form URL
            submission {Dict} -- The submission data

        Returns:
            str -- The unique ID of the new submission
        """
        formio_token = self.generate_formio_token()
        with session_with_auth(
            token=formio_token, token_header_key="x-jwt-token"
        ) as session:
            response = session.post(form_url, json=submission)
            print(response)
            if response.status_code != HTTPStatus.CREATED:
                raise Exception(
                    f"Failed to create submission. API response: {response.json()}"
                )
            print(response.json())
            new_submission = response.json()
            return new_submission["_id"]

    def get_submission_url(self, form_url: str) -> str:
        """Generates the form submission URL from form_url

        Arguments:
            form_url {str} -- FormIO url

        Returns:
            str -- FormIO submission endpoint for the form
        """
        if form_url.endswith("submission"):
            return form_url
        return substring_before_last(form_url, "/")
