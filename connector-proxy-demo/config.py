
from os import environ
from typing import Any
from flask import current_app


def config_from_env(variable_name: str, *, default: str | bool | int | None = None) -> Any:
    value_from_env: str | None = environ.get(variable_name)
    if value_from_env == "":
        value_from_env = None

    value_to_return: str | bool | int | None = value_from_env
    # using docker secrets - put file contents to env value
    if variable_name.endswith("_FILE"):
        value_from_file = default if value_from_env is None else value_from_env
        if value_from_file:
            if isinstance(value_from_file, str) and value_from_file.startswith("/run/secrets"):
                # rewrite variable name: remove _FILE
                variable_name = variable_name.removesuffix("_FILE")
                try:
                    with open(value_from_file) as file:
                        value_to_return = file.read().strip()  # Read entire content and strip any extra whitespace
                except FileNotFoundError:
                    value_to_return = None  # Handle the case where the file does not exist
                except Exception as e:
                    current_app.logger.error(f"Error reading from {value_from_file}: {str(e)}")
                    value_to_return = None  # Handle other potential errors

    if value_from_env is not None:
        if isinstance(default, bool):
            if value_from_env.lower() == "true":
                value_to_return = True
            if value_from_env.lower() == "false":
                value_to_return = False
        elif isinstance(default, int):
            value_to_return = int(value_from_env)

    if value_to_return is None:
        value_to_return = default

    # NOTE: using this method in other config python files will NOT overwrite
    # the value set in the variable here. It is better to set the variables like
    # normal in them so they can take effect.
    globals()[variable_name] = value_to_return
    return value_to_return


config_from_env("FF_WEB_API_URL", default="http://localhost:5000")
config_from_env("BPM_TOKEN_API", default="")
config_from_env("BPM_CLIENT_ID", default="forms-flow-bpm")
config_from_env("BPM_CLIENT_SECRET", default="")
config_from_env("BPM_GRANT_TYPE", default="client_credentials")
config_from_env("SPIFFWORKFLOW_BACKEND_OPEN_ID_SERVER_URL", default="")
config_from_env("SPIFFWORKFLOW_BACKEND_OPEN_ID_CLIENT_ID", default="")
config_from_env("SPIFFWORKFLOW_BACKEND_OPEN_ID_CLIENT_SECRET_KEY", default="")
config_from_env("SPIFFWORKFLOW_BACKEND_OPEN_ID_VERIFY_IAT", default=True)
config_from_env("SPIFFWORKFLOW_BACKEND_OPEN_ID_VERIFY_NBF", default=True)
config_from_env("SPIFFWORKFLOW_BACKEND_OPEN_ID_LEEWAY", default=5)
config_from_env("FORMIO_USERNAME")
config_from_env("FORMIO_PASSWORD")
config_from_env("FORMIO_URL")
config_from_env("SPIFF_BACKEND_URL")
