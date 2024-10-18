from typing import Any
import time
from datetime import datetime
from typing import Any
from sqlalchemy import and_, asc, desc, cast
from sqlalchemy.types import String

import flask.wrappers
import sentry_sdk
from SpiffWorkflow.bpmn.exceptions import WorkflowTaskException  # type: ignore
from SpiffWorkflow.bpmn.workflow import BpmnWorkflow  # type: ignore
from SpiffWorkflow.task import Task as SpiffTask  # type: ignore
from SpiffWorkflow.util.task import TaskState  # type: ignore
from flask import current_app
from flask import g
from flask import jsonify
from flask import make_response
from spiffworkflow_backend.exceptions.api_error import ApiError
from spiffworkflow_backend.models.db import SpiffworkflowBaseDBModel
from spiffworkflow_backend.models.db import db
from spiffworkflow_backend.models.group import GroupModel
from spiffworkflow_backend.models.human_task import HumanTaskModel
from spiffworkflow_backend.models.task import TaskModel
from spiffworkflow_backend.models.human_task_user import HumanTaskUserModel
from spiffworkflow_backend.models.process_instance import ProcessInstanceModel
from spiffworkflow_backend.models.process_instance import ProcessInstanceStatus
from spiffworkflow_backend.models.process_model import ProcessModelInfo
from spiffworkflow_backend.models.user import UserModel
from spiffworkflow_backend.models.json_data import JsonDataModel
from spiffworkflow_backend.routes.process_api_blueprint import _task_submit_shared
from sqlalchemy import and_
from sqlalchemy import desc
from sqlalchemy import func

from .tasks_controller import task_assign


def filter_tasks(body: dict, firstResult: int = 1, maxResults: int = 100) -> flask.wrappers.Response:
    """Filter tasks and return the list."""
    if not body or body.get('criteria') is None:
        return None
    user_model: UserModel = g.user

    human_tasks_query = (
        db.session.query(
            HumanTaskModel, ProcessInstanceModel.id, ProcessModelInfo,
            func.max(UserModel.username).label("process_initiator_username"),
            func.max(UserModel.display_name).label("process_initiator_firstname"),
            func.max(UserModel.email).label("process_initiator_email"),
            func.max(GroupModel.identifier).label("assigned_user_group_identifier")
        ).distinct(HumanTaskModel.id)
        .group_by(
            HumanTaskModel.id,  # Group by the ID of the human task
            ProcessInstanceModel.id,  # Add the process instance ID to the GROUP BY clause
            ProcessModelInfo.process_id,
            # GroupModel.identifier
        )  # type: ignore
        .outerjoin(GroupModel, GroupModel.id == HumanTaskModel.lane_assignment_id)
        .join(ProcessInstanceModel)
        .join(ProcessModelInfo, ProcessModelInfo.id == ProcessInstanceModel.process_model_identifier)
        .outerjoin(HumanTaskUserModel, and_(
            HumanTaskModel.id == HumanTaskUserModel.human_task_id,
            HumanTaskUserModel.ended_at_in_seconds == None
        ))
        .outerjoin(UserModel, UserModel.id == HumanTaskUserModel.user_id)
        .outerjoin(TaskModel, TaskModel.guid == HumanTaskModel.task_id)
        .outerjoin(JsonDataModel, JsonDataModel.hash == TaskModel.json_data_hash)
        .filter(
            HumanTaskModel.completed == False,  # noqa: E712
            ProcessInstanceModel.status != ProcessInstanceStatus.error.value,
        )
    )

    # Join through HumanTaskUserModel to associate users to tasks
    if body.get('criteria').get('candidateGroupsExpression') == '${currentUserGroups()}':
        human_tasks_query = human_tasks_query.filter(
            GroupModel.identifier.in_([group.identifier for group in user_model.groups]))
    if candidate_group := body.get('criteria').get('candidateGroup'):
        human_tasks_query = human_tasks_query.filter(GroupModel.identifier == candidate_group)
    if not body.get('criteria').get('includeAssignedTasks', False):
        human_tasks_query = human_tasks_query.filter(~HumanTaskModel.human_task_users.any())

    if process_def_key := body.get('criteria').get('processDefinitionKey'):
        human_tasks_query = human_tasks_query.filter(ProcessInstanceModel.process_model_identifier == process_def_key)
    if ''.join(body.get('criteria').get('assigneeExpression', '').split()) == '${currentUser()}':
        human_tasks_query = human_tasks_query.filter(UserModel.username == user_model.username)
    if assignee := body.get('criteria').get('assignee'):
        human_tasks_query = human_tasks_query.filter(UserModel.username == assignee)
    if assignee := body.get('criteria').get('assignee'):
        human_tasks_query = human_tasks_query.filter(UserModel.username == assignee)

    #  Filtering by process variables
    process_variables = body.get('criteria', {}).get('processVariables', [])
    if process_variables:
        for variable in process_variables:
            var_name = variable.get('name')
            var_value = variable.get('value')
            json_field = JsonDataModel.data['data'].op('->>')(var_name)
            human_tasks_query = human_tasks_query.filter(cast(json_field, String) == var_value)

    # Sorting logic
    sorting_criteria = body.get('criteria', {}).get('sorting', [])
    if sorting_criteria:
        for sort_item in sorting_criteria:
            sort_by = sort_item.get('sortBy')
            sort_order = sort_item.get('sortOrder', 'asc')  # Default to ascending if not provided

            if sort_by == 'created':
                human_tasks_query = human_tasks_query.order_by(
                    asc(HumanTaskModel.id),
                    asc(HumanTaskModel.created_at_in_seconds) if sort_order == 'asc' else desc(HumanTaskModel.created_at_in_seconds)
                )
            elif sort_by == 'title':
                human_tasks_query = human_tasks_query.order_by(
                    asc(HumanTaskModel.id),
                    asc(HumanTaskModel.task_title) if sort_order == 'asc' else desc(HumanTaskModel.task_title)
                )

    else:
        human_tasks_query = human_tasks_query.order_by(desc(HumanTaskModel.id))  # Order by task ID

    current_app.logger.info("human_tasks_query --->")
    current_app.logger.info(human_tasks_query)

    human_tasks = human_tasks_query.paginate(page=firstResult, per_page=maxResults, error_out=False)

    return _format_response(human_tasks)


def get_task_by_id(
        task_id: str
) -> flask.wrappers.Response:
    # Query to join HumanTaskModel with HumanTaskUserModel
    task_query = (
        db.session.query(HumanTaskModel, HumanTaskUserModel, UserModel)
        .join(HumanTaskUserModel, and_(HumanTaskModel.id == HumanTaskUserModel.human_task_id,
                                       HumanTaskUserModel.ended_at_in_seconds == None))
        .join(UserModel, HumanTaskUserModel.user_id == UserModel.id)  # Join with UserModel to get user details
        .filter(HumanTaskModel.task_guid == task_id)
    )

    tasks = task_query.all()

    # If no tasks are found, return an empty list
    if not tasks:
        raise ApiError(
            error_code="task_not_found",
            message=f"Cannot find a task with id '{task_id}'",
            status_code=400,
        )
    if not len(tasks) > 1:
        raise ApiError(
            error_code="more_than_one_task_found",
            message=f"More tasks found for '{task_id}'",
            status_code=400,
        )
    human_task, human_task_user, user_model = tasks[0]
    return make_response(jsonify(format_human_task_response(human_task, user_model)), 200)


def claim_task(
        task_id: str,
        body: dict[str, Any],
) -> flask.wrappers.Response:
    task_model: HumanTaskModel | None = HumanTaskModel.query.filter_by(id=task_id).one_or_none()
    if task_model is None:
        raise ApiError(
            error_code="task_not_found",
            message=f"Cannot find a task with id '{task_id}'",
            status_code=400,
        )

    task_assign(modified_process_model_identifier=None, process_instance_id=task_model.process_instance_id,
                task_guid=task_model.task_guid, body={'user_ids': [body.get("userId")]})

    return make_response(jsonify(format_human_task_response(task_model)), 200)


def unclaim_task(
        task_id: str,
        body: dict[str, Any],
) -> flask.wrappers.Response:
    task_model: HumanTaskModel | None = HumanTaskModel.query.filter_by(id=task_id).one_or_none()
    if task_model is None:
        raise ApiError(
            error_code="task_not_found",
            message=f"Cannot find a task with id '{task_id}'",
            status_code=400,
        )

    # formsflow.ai allows only one user per task.
    human_task_users = HumanTaskUserModel.query.filter_by(ended_at_in_seconds=None, human_task=task_model).all()
    for human_task_user in human_task_users:
        human_task_user.ended_at_in_seconds = round(time.time())

    SpiffworkflowBaseDBModel.commit_with_rollback_on_exception()

    return make_response(jsonify({"ok": True}), 200)


def get_task_variables(  # TODO
        task_id: int
) -> flask.wrappers.Response:
    pass


def get_task_identity_links(  # TODO
        task_id: int
) -> flask.wrappers.Response:
    pass


def submit_task(
        task_id: str,
        body: dict[str, Any],
) -> flask.wrappers.Response:
    task_model: HumanTaskModel | None = HumanTaskModel.query.filter_by(id=task_id).one_or_none()
    if task_model is None:
        raise ApiError(
            error_code="task_not_found",
            message=f"Cannot find a task with id '{task_id}'",
            status_code=400,
        )
    # TODO Manage task variables submitted.
    with sentry_sdk.start_span(op="controller_action", description="tasks_controller.task_submit"):
        response_item = _task_submit_shared(task_model.process_instance_id, task_model.task_guid, body)
        return make_response(jsonify(response_item), 200)


def _format_response(human_tasks):
    response = []

    tasks = []
    for task in human_tasks.items:
        task_data = {
            "_links": {
                # Empty _links as spiff doesn't support HATEOAS
            },
            "_embedded": {
                "candidateGroups": [
                    {
                        "_links": {
                            "group": {
                                "href": f"/group/{task.assigned_user_group_identifier}"
                            },
                            "task": {
                                "href": f"/task/{task.HumanTaskModel.id}"
                            }
                        },
                        "_embedded": None,
                        "type": "candidate",
                        "userId": None,
                        "groupId": task.assigned_user_group_identifier,
                        "taskId": task.HumanTaskModel.id
                    }
                ],
                "variable": [
                    task.HumanTaskModel.task_model.get_data()  # TODO adjust to match with Camunda response
                ]
            },
            "id": task.HumanTaskModel.task_guid,
            "name": task.HumanTaskModel.task_title,
            "assignee": task.process_initiator_username,
            "created": datetime.utcfromtimestamp(task.HumanTaskModel.created_at_in_seconds).isoformat() + 'Z',
            "due": None,  # TODO
            "followUp": None,  # TODO
            "delegationState": None,
            "description": None,
            "executionId": task.HumanTaskModel.process_instance_id,
            "owner": None,
            "parentTaskId": None,
            "priority": 50,  # TODO: Dynamically set this value
            "processDefinitionId": task.ProcessModelInfo.process_id,
            "processInstanceId": task.HumanTaskModel.process_instance_id,
            "taskDefinitionKey": task.HumanTaskModel.task_id,
            "caseExecutionId": None,
            "caseInstanceId": None,
            "caseDefinitionId": None,
            "suspended": False,
            "formKey": None,
            "camundaFormRef": None,
            "tenantId": None
        }

        tasks.append(task_data)

    # Remove duplicates from the assignees list based on unique username
    assignees = list({
                         task.process_initiator_username: {
                             "_links": {
                                 "self": {
                                     "href": f"/user/{task.process_initiator_username}"
                                 }
                             },
                             "_embedded": None,
                             "id": task.process_initiator_username,
                             "firstName": task.process_initiator_firstname,
                             "lastName": "",  # Replace with actual data if available
                             "email": task.process_initiator_email
                         }
                         for task in human_tasks.items
                     }.values())

    # Remove duplicates from processDefinition list based on unique process ID
    process_definitions = list({
                                   task.ProcessModelInfo.id: {
                                       "_links": {},
                                       "_embedded": None,
                                       "id": task.ProcessModelInfo.id,
                                       "key": task.ProcessModelInfo.process_id,
                                       "category": "http://bpmn.io/schema/bpmn",
                                       "description": task.ProcessModelInfo.description,
                                       "name": task.ProcessModelInfo.display_name,
                                       "versionTag": "1",  # TODO Replace with actual version if available
                                       "version": 1,  # TODO Replace with actual version if available
                                       "resource": f"{task.ProcessModelInfo.display_name}.bpmn",
                                       "deploymentId": task.ProcessModelInfo.id,
                                       "diagram": None,
                                       "suspended": False,
                                       "contextPath": None
                                   }
                                   for task in human_tasks.items
                               }.values())

    response.append({
        "_links": {},
        "_embedded": {
            "assignee": assignees,
            "processDefinition": process_definitions,
            "task": tasks
        },
        "count": human_tasks.total
    })

    response.append({  # Additional information about variables
        "variables": [
            {
                "name": "formName",
                "label": "Form Name"
            },
            {
                "name": "applicationId",
                "label": "Submission Id"
            }
        ],
        "taskVisibleAttributes": {
            "applicationId": True,
            "assignee": True,
            "taskTitle": True,
            "createdDate": True,
            "dueDate": True,
            "followUp": True,
            "priority": True,
            "groups": True
        }
    })

    return make_response(jsonify(response), 200)


def format_human_task_response(human_task: HumanTaskModel, user_model: UserModel) -> dict:
    """
    Format the human_task into the required response structure.
    """
    return {
        "id": human_task.task_guid,
        "name": human_task.task_title or human_task.task_name,
        "assignee": user_model.username,
        "created": datetime.utcfromtimestamp(
            human_task.created_at_in_seconds).isoformat() + "Z" if human_task.created_at_in_seconds else None,
        "due": None,  # TODO
        "followUp": None,  # TODO
        "description": human_task.task_name,  # Assuming task_name serves as the description
        "parentTaskId": None,  # No clear parent task id field in the model
        "priority": 50,  # Default to 50 since there's no priority field in the model
        "processDefinitionId": human_task.bpmn_process_identifier,  # Mapping to bpmn_process_identifier
        "processInstanceId": human_task.process_instance_id,
        "taskDefinitionKey": human_task.task_id,  # Mapping taskDefinitionKey to task_id
        "tenantId": None  # TODO
    }
