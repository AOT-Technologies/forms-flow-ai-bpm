from http import HTTPStatus
from typing import Dict
from flask import current_app

from connector_formsflow.services.external.authentication_service import (
    session_with_auth,
)
from connector_formsflow.services.utils.helpers import get_token_info
from connector_formsflow.services.utils.type_defs import UpdateTaskDataPayload


class SpiffBackendService:
    """Implements web api calls"""

    spiff_backend_url = f"{current_app.config.get('SPIFF_BACKEND_URL')}/v1.0"

    @classmethod
    def update_task_data(cls, task_guid: str, payload: UpdateTaskDataPayload):
        """Updates task for given task

        Arguments:
            task_guid {str} -- unique ID of the task
        """

        url = f"{cls.spiff_backend_url}/task/{task_guid}/update-data"
        token = get_token_info()
        with session_with_auth(token) as session:
            response = session.put(url, json=payload)
            if response.status_code != HTTPStatus.OK:
                raise Exception(
                    f"Failed to update task data. API response: {response.json()}"
                )
            return response.json()
