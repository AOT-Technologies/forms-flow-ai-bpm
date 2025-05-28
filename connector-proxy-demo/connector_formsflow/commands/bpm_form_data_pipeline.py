from http import HTTPStatus
from typing import Dict, List
from spiffworkflow_connector_command.command_interface import CommandErrorDict
from spiffworkflow_connector_command.command_interface import ConnectorCommand
from spiffworkflow_connector_command.command_interface import ConnectorProxyResponseDict
from spiffworkflow_connector_command.command_interface import CommandResponseDict

from connector_formsflow.services.external.formio_service import FormIOService
from connector_formsflow.services.utils.type_defs import PatchSubmissionItem, TaskData


class BPMFormDataPipeline(ConnectorCommand):

    def __init__(self, fields: List[str] = None):
        self.fields = fields
        super().__init__()

    def execute(self, config, task_data: TaskData):
        error: CommandErrorDict | None = None
        logs = []
        try:
            logs.append("Patching form data")
            payload = self._prepare_payload(task_data, self.fields)
            form_url = task_data["data"]["formUrl"]  # type: ignore
            logs.append("Calling FormIO api")
            response_json, status_code = FormIOService().patch_form_attributes(
                form_url, payload
            )
            logs.append(f"Response from api {response_json}")
            if status_code != HTTPStatus.OK:
                error = {
                    "error_code": "API_CALL_FAILED",
                    "message": f"FormIO API call failed. {response_json = }",
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
        self, task_data: Dict, fields: List[str]
    ) -> List[PatchSubmissionItem]:
        """Prepare the fields in the format expected by FormIO

        Arguments:
            task_data {Dict} -- task data available to the workflow
            fields {List} -- List of fields to be patched

        Returns:
            List -- Fields and corresponding values
        """
        data: List[PatchSubmissionItem] = [
            {
                "op": "replace",
                "path": f"/data/{field}",
                "value": task_data["data"].get(field),
            }
            for field in fields
        ]
        return data
