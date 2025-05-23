from http import HTTPStatus
import json
from typing import Dict, List
from spiffworkflow_connector_command.command_interface import CommandErrorDict
from spiffworkflow_connector_command.command_interface import ConnectorCommand
from spiffworkflow_connector_command.command_interface import ConnectorProxyResponseDict
from spiffworkflow_connector_command.command_interface import CommandResponseDict

from connector_formsflow.services.external.formio_service import FormIOService
from connector_formsflow.services.external.spiff_api_service import SpiffBackendService
from connector_formsflow.services.external.web_api_service import WebAPIService
from connector_formsflow.services.utils.type_defs import TaskData, UpdateTaskDataPayload


class FormBPMFilteredDataPipeline(ConnectorCommand):

    def __init__(self):
        super().__init__()

    def execute(self, config, task_data: TaskData):
        error: CommandErrorDict | None = None
        logs = []
        try:
            logs.append("Syncing form data")
            payload = self._prepare_payload(task_data)
            logs.append("Calling task update api")
            response_json, status_code = SpiffBackendService.update_task_data(
                task_data["task_guid"], payload  # type: ignore
            )
            logs.append(f"Response from api {response_json}")
            if status_code != HTTPStatus.OK:
                error = {
                    "error_code": "API_CALL_FAILED",
                    "message": f"Spiff API call failed. {response_json = }",
                }
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

    def _prepare_payload(self, task_data: TaskData) -> UpdateTaskDataPayload:
        """Prepare the fields in the format expected by the API

        Arguments:
            task_data {Dict} -- task data available to the workflow

        Returns:
            List -- Fields and corresponding values
        """
        application_id = task_data["data"]["applicationId"]  # type: ignore
        application = WebAPIService.fetch_application_details(application_id)
        task_variables = json.loads(application["taskVariables"])
        task_variables = [x["key"] for x in task_variables]

        form_url = task_data["data"]["formUrl"]  # type: ignore
        submission = FormIOService().fetch_submission(form_url)
        submission_data = submission["data"]
        payload = task_data
        for variable in task_variables:
            payload["data"][variable] = submission_data[variable]
        return {"new_task_data": payload}
