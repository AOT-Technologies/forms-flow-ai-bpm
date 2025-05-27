from typing import Any
import time
import json
import copy
from datetime import datetime
from typing import Any, Dict
from sqlalchemy import and_, asc, desc, cast
from sqlalchemy.types import String
from hashlib import sha256

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


def filter_tasks(body: Dict, firstResult: int = 1, maxResults: int = 100) -> flask.wrappers.Response:
    """Filter tasks and return the list and count."""
    if not body or body.get('criteria') is None:
        return None
    user_model: UserModel = g.user

    human_tasks_query = build_human_tasks_query(body, user_model)

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

    # Paginate results for task retrieval
    page = (firstResult // maxResults) + 1
    human_tasks = human_tasks_query.paginate(page=page, per_page=maxResults, error_out=False)

    return _format_response(human_tasks)

def filter_tasks_count(body: Dict) -> flask.wrappers.Response:
    """Filter tasks and return only the count."""
    user_model: UserModel = g.user
    response = []

    for criteria in body:
        if not criteria or criteria.get('criteria') is None:
            return None

        human_tasks_query = build_human_tasks_query(criteria, user_model)

        # Get the total count of tasks
        task_count = human_tasks_query.count()
        response.append({
            "name": criteria.get("name"),
            "count": task_count,
            "id": criteria.get("id")
        })

    return response


def build_human_tasks_query(body: Dict, user_model: UserModel):
    """Build the base query for filtering tasks."""
    human_tasks_query = (
        db.session.query(
            HumanTaskModel,
            ProcessInstanceModel.id,
            ProcessModelInfo,
            func.max(UserModel.username).label("process_initiator_username"),
            func.max(UserModel.display_name).label("process_initiator_firstname"),
            func.max(UserModel.email).label("process_initiator_email"),
            func.max(GroupModel.identifier).label("assigned_user_group_identifier"),
        )
        .distinct(HumanTaskModel.id)
        .group_by(
            HumanTaskModel.id,  # Group by the ID of the human task
            ProcessInstanceModel.id,  # Add the process instance ID to the GROUP BY clause
            ProcessModelInfo.process_id,
        )
        .outerjoin(GroupModel, GroupModel.id == HumanTaskModel.lane_assignment_id)
        .join(ProcessInstanceModel)
        .join(
            ProcessModelInfo,
            ProcessModelInfo.id == ProcessInstanceModel.process_model_identifier,
        )
        .outerjoin(
            HumanTaskUserModel,
            and_(
                HumanTaskModel.id == HumanTaskUserModel.human_task_id,
                HumanTaskUserModel.ended_at_in_seconds == None,
            ),
        )
        .outerjoin(UserModel, UserModel.id == HumanTaskUserModel.user_id)
        .outerjoin(TaskModel, TaskModel.guid == HumanTaskModel.task_id)
        .outerjoin(JsonDataModel, JsonDataModel.hash == TaskModel.json_data_hash)
        .filter(
            HumanTaskModel.completed == False,  # noqa: E712
            ProcessInstanceModel.status != ProcessInstanceStatus.error.value,
        )
    )

    # Apply filters based on body criteria
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

    # Filtering by process variables
    process_variables = body.get('criteria', {}).get('processVariables', [])
    if process_variables:
        for variable in process_variables:
            var_name = variable.get('name')
            var_value = variable.get('value')
            json_field = JsonDataModel.data['data'].op('->>')(var_name)
            human_tasks_query = human_tasks_query.filter(cast(json_field, String).ilike(f"%{var_value}%"))

    return human_tasks_query


def get_task_variables_by_id(
        task_id: str
) -> flask.wrappers.Response:
    current_app.logger.debug("get_task_variables_by_id --->%s", task_id)

    task : TaskModel = db.session.query(TaskModel).filter(TaskModel.guid == task_id).one_or_none()

    # If no tasks are found, return an empty list
    if not task:
        raise ApiError(
            error_code="task_not_found",
            message=f"Cannot find a task with id '{task_id}'",
            status_code=400,
        )
    response = {}
    for key in task.get_data().get("data").keys():
        response[key] = {
            "type" : "String", #TODO
            "value": task.get_data().get("data").get(key)
        }
    return response

def get_task_identity_links_by_id(
        task_id: str
) -> flask.wrappers.Response:
    current_app.logger.debug("get_task_identity_links_by_id --->%s", task_id)
    db.session.query(HumanTaskModel, UserModel, GroupModel)
    task_query = (
        db.session.query(HumanTaskModel, UserModel, GroupModel)
        .outerjoin(HumanTaskUserModel, and_(HumanTaskModel.id == HumanTaskUserModel.human_task_id,
                                       HumanTaskUserModel.ended_at_in_seconds == None))
        .outerjoin(UserModel, HumanTaskUserModel.user_id == UserModel.id)  # Join with UserModel to get user details
        .outerjoin(GroupModel, GroupModel.id == HumanTaskModel.lane_assignment_id)
        .filter(HumanTaskModel.task_guid == task_id)
    )
    tasks = task_query.all()

    human_task, user, group = tasks[0]
    response = [{
            "userId": user.username if user else None,
            "groupId": group.identifier,
            "type": "candidate"

    }]


    return response

def get_task_by_id(
        task_id: str
) -> flask.wrappers.Response:
    current_app.logger.debug("get_task_by_id --->%s", task_id)

    task_query = (
        db.session.query(HumanTaskModel, HumanTaskUserModel, UserModel)
        .outerjoin(HumanTaskUserModel, and_(HumanTaskModel.id == HumanTaskUserModel.human_task_id,
                                       HumanTaskUserModel.ended_at_in_seconds == None))
        .outerjoin(UserModel, HumanTaskUserModel.user_id == UserModel.id)  # Join with UserModel to get user details
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
    if len(tasks) > 1:
        raise ApiError(
            error_code="more_than_one_task_found",
            message=f"More tasks found for '{task_id}'",
            status_code=400,
        )
    human_task, human_task_user, user_model = tasks[0]
    return make_response(jsonify(format_human_task_response(human_task, user_model)), 200)


def claim_task(
        task_id: str,
        body: Dict[str, Any],
) -> flask.wrappers.Response:
    task_model: HumanTaskModel | None = HumanTaskModel.query.filter_by(task_guid=task_id).one_or_none()
    if task_model is None:
        raise ApiError(
            error_code="task_not_found",
            message=f"Cannot find a task with id '{task_id}'",
            status_code=400,
        )
    user_model: UserModel = UserModel.query.filter_by(username=body.get("userId")).one_or_none()
    if user_model is None: #TODO decide if we need to create a dummy user in this case.
        raise ApiError(
            error_code="user_not_found",
            message=f"Cannot find a user with id '{task_id}'",
            status_code=400,
        )

    task_assign(modified_process_model_identifier=None, process_instance_id=task_model.process_instance_id,
                task_guid=task_model.task_guid, body={'user_ids': [user_model.id]})

    return {}


def unclaim_task(
        task_id: str,
        body: Dict[str, Any],
) -> flask.wrappers.Response:
    task_model: HumanTaskModel | None = HumanTaskModel.query.filter_by(task_guid=task_id).one_or_none()
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


def submit_task(
        task_id: str,
        body: Dict[str, Any],
) -> flask.wrappers.Response:
    human_task_model: HumanTaskModel | None = HumanTaskModel.query.filter_by(task_guid=task_id).one_or_none()
    if human_task_model is None:
        raise ApiError(
            error_code="task_not_found",
            message=f"Cannot find a task with id '{task_id}'",
            status_code=400,
        )
    # Manage task variables submitted.
    task_model: TaskModel = TaskModel.query.filter_by(guid=task_id).one_or_none()
    # First update the variables and then submit task
    data = copy.deepcopy(task_model.get_data())
    for var in body.get("variables").keys():
        data["data"][var] = body.get("variables")[var]["value"]

    json_data_hash = sha256(json.dumps(data).encode("utf8")).hexdigest()
    json_data_model = JsonDataModel(hash=json_data_hash, data=data)
    db.session.add(json_data_model)
    db.session.flush()
    task_model.json_data_hash = json_data_hash
    with sentry_sdk.start_span(op="controller_action", description="tasks_controller.task_submit"):
        response_item = _task_submit_shared(task_model.process_instance_id, task_model.guid, body)
        return make_response(jsonify(response_item), 200)


def _format_task_variables(task_data: Dict):
    variables = []
    for key in task_data.get("data"):
        variables.append({
            "name": key,
            "value": task_data.get("data")[key],
            "type": "String" #TODO Dynamically derive this from the element value
        })
    return variables


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
                "variable": _format_task_variables(task.HumanTaskModel.task_model.get_data())
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
    assignees = list(
        {
            task.process_initiator_username: {
                "_links": {
                    "self": {"href": f"/user/{task.process_initiator_username}"}
                },
                "_embedded": None,
                "id": task.process_initiator_username,
                "firstName": task.process_initiator_firstname,
                "lastName": "",  # Replace with actual data if available
                "email": task.process_initiator_email,
            }
            for task in human_tasks.items
        }.values()
    )

    # Remove duplicates from processDefinition list based on unique process ID
    process_definitions = list(
        {
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
                "contextPath": None,
            }
            for task in human_tasks.items
        }.values()
    )

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
        "assignee": user_model.username if user_model else None,
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
