from http import HTTPStatus
from typing import Dict
from spiffworkflow_connector_command.command_interface import CommandErrorDict
from spiffworkflow_connector_command.command_interface import ConnectorCommand
from spiffworkflow_connector_command.command_interface import ConnectorProxyResponseDict
from spiffworkflow_connector_command.command_interface import CommandResponseDict

from connector_formsflow.commands.application_audit import ApplicationAudit
from connector_formsflow.services.external.web_api_service import WebAPIService
from connector_formsflow.services.utils.helpers import get_submitted_by
from connector_formsflow.services.utils.type_defs import ApplicationStatePayload, TaskData


class ApplicationState(ConnectorCommand):

    def __init__(self, status: str = None):
        self.status = status
        super().__init__()

    def execute(self, config, task_data: TaskData):
        error: CommandErrorDict | None = None
        logs = []
        try:
            logs.append("Updating status")
            logs.append("Preparing payload")
            payload = self._prepare_payload(task_data)
            logs.append("Calling API")
            application_id = task_data["data"]["applicationId"] # type: ignore
            response_json, status_code = WebAPIService.update_application_state(
                application_id, payload
            )
            logs.append(f"Response from web api {response_json}")
            if status_code == HTTPStatus.OK:
                ApplicationAudit(self.status).execute(config, task_data)
        except Exception as exception:
            logs.append(f"did error: {str(exception)}")
            error = {
                "error_code": exception.__class__.__name__,
                "message": str(exception),
            }

        return_response: CommandResponseDict = {
            "body": "{}",
            "mimetype": "application/json",
        }
        result: ConnectorProxyResponseDict = {
            "command_response": return_response,
            "error": error,
            "command_response_version": 2,
            "spiff__logs": logs,
        }

        return result

    def _prepare_payload(self, task_data: TaskData) -> ApplicationStatePayload:
        """Prepare the web api payload from task data

        Arguments:
            task_data {Dict} -- The task data available to the workflow

        Returns:
            Dict -- Payload for web API
        """
        submitted_by = get_submitted_by(task_data)
        payload:ApplicationStatePayload = {
            "applicationStatus": self.status,
            "formUrl": task_data["data"].get("formUrl"), # type: ignore
            "isResubmit": bool(task_data["data"].get("isResubmit", None)),
            "eventName": task_data["data"].get("eventName", None),
            "submittedBy": submitted_by,
        }
        return payload
