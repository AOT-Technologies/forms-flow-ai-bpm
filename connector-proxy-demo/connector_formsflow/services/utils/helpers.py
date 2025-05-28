from typing import Dict

from flask import request

from connector_formsflow.services.external.authentication_service import (
    AuthenticationService,
)
from connector_formsflow.services.utils.type_defs import TaskData


def get_token_info() -> str | None:
    """Decode and return the token info from headers"""
    try:
        token = request.headers["Authorization"].removeprefix("Bearer ")
    except KeyError:
        return None
    if token:
        return token
    return None


def get_submitted_by(task_data: TaskData) -> str:
    """Return submitted by username
    Arguments:
        task_data {Dict} -- the task data available to the workflow

    Returns:
        str -- submitted by username
    """
    token = get_token_info()
    decoded_token = AuthenticationService.parse_jwt_token("default", token)
    if decoded_token:
        submitted_by = decoded_token["preferred_username"]
        if submitted_by.startswith("service-account"):
            submitted_by = "Anonymous-User"
    else:
        submitted_by = task_data["data"].get("currentUser", None)
    return submitted_by


def substring_before_last(string: str, char: str) -> str:
    """Generates a substring upto the last occurrence of given character 

    Arguments:
        string {str} -- Original string
        char {str} -- delimiter 

    Returns:
        str -- A substring of 'string' from 0 - last index of 'char'
    """
    if string.endswith("submission"):
        return string
    index = string.rfind(char)  # Returns the highest index where 'char' is found
    return string[:index] if index != -1 else string
