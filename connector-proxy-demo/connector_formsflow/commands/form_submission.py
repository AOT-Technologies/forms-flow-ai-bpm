from http import HTTPStatus
from typing import Dict
from spiffworkflow_connector_command.command_interface import CommandErrorDict
from spiffworkflow_connector_command.command_interface import ConnectorCommand
from spiffworkflow_connector_command.command_interface import ConnectorProxyResponseDict
from spiffworkflow_connector_command.command_interface import CommandResponseDict

from connector_formsflow.services.external.formio_service import FormIOService
from connector_formsflow.services.external.spiff_api_service import SpiffBackendService
from connector_formsflow.services.utils.type_defs import TaskData, UpdateTaskDataPayload


class FormSubmission(ConnectorCommand):

    def __init__(self):
        super().__init__()

    def execute(self, config, task_data: TaskData):
        error: CommandErrorDict | None = None
        logs = []
        try:
            logs.append("Creating submission")
            logs.append("Fetching last submission")
            formio_service = FormIOService()
            form_url = task_data["data"]["formUrl"]  # type: ignore
            submission = formio_service.fetch_submission(form_url)
            logs.append("Creating revision")
            submission_url = formio_service.get_submission_url(form_url)

            logs.append("Calling FormIO api")
            revision_id = formio_service.create_revision(submission_url, submission)
            logs.append(f"{revision_id = }")
            logs.append("Updating task data")
            payload = self._prepare_payload(task_data, revision_id)
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

    def _prepare_payload(
        self, task_data: TaskData, submission_id: str
    ) -> UpdateTaskDataPayload:
        """Prepare the fields in the format expected by FormIO

        Arguments:
            task_data {TaskData} -- task data available to the workflow
            submission_id {int} -- ID of new revision

        Returns:
            Dict -- Payload for FormIO submission API
        """
        form_io_service = FormIOService()
        form_url = form_io_service.get_submission_url(task_data["data"]["formUrl"])  # type: ignore
        web_form_url = form_io_service.get_submission_url(
            task_data["data"]["webFormUrl"]  # type: ignore
        )
        payload = task_data
        payload["data"]["formUrl"] = f"{form_url}/{submission_id}"
        if web_form_url:
            payload["data"]["webFormUrl"] = f"{web_form_url}/{submission_id}"
        return {"new_task_data": payload}
