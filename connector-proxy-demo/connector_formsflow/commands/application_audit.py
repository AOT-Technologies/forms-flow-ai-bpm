from typing import Dict
from spiffworkflow_connector_command.command_interface import CommandErrorDict
from spiffworkflow_connector_command.command_interface import ConnectorCommand
from spiffworkflow_connector_command.command_interface import ConnectorProxyResponseDict
from spiffworkflow_connector_command.command_interface import CommandResponseDict

from connector_formsflow.services.external.web_api_service import WebAPIService
from connector_formsflow.services.utils.helpers import get_submitted_by
from connector_formsflow.services.utils.type_defs import ApplicationAuditPayload, TaskData


class ApplicationAudit(ConnectorCommand):

    def __init__(self, status: str = None):
        self.status = status
        super().__init__()

    def execute(self, config, task_data: TaskData):
        error: CommandErrorDict | None = None
        logs = []
        try:
            logs.append("Creating audit history")
            logs.append("Preparing payload")
            payload = self._prepare_payload(task_data)
            logs.append("Calling API")
            application_id = task_data["data"]["applicationId"] # type: ignore
            response_json, _ = WebAPIService.create_application_audit(
                application_id, payload
            )
            logs.append(f"Response from web api {response_json}")
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

    def _prepare_payload(self, task_data: TaskData) -> ApplicationAuditPayload:
        """Prepare the payload for Web API

        Arguments:
            task_data {Dict} -- Task data available to the workflow

        Returns:
            Dict -- Payload for the Application audit API
        """
        submitted_by = get_submitted_by(task_data)
        payload: ApplicationAuditPayload = {
            "applicationStatus": self.status,
            "formUrl": task_data["data"].get("formUrl"), # type: ignore
            "color": task_data["data"].get("color", None),
            "percentage": task_data["data"].get("percentage", None),
            "submittedBy": submitted_by,
        }
        return payload
