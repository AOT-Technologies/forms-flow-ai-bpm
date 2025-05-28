import os

from spiffworkflow_proxy.blueprint import proxy_blueprint
from flask import Flask
from dotenv import find_dotenv, load_dotenv


# this will load all the envars from a .env file located in the project root (api)
load_dotenv(find_dotenv())


app = Flask(__name__)
app.config.from_pyfile("config.py", silent=True)
app.config["SPIFFWORKFLOW_BACKEND_AUTH_CONFIGS"] = [
    {
        "identifier": "default",
        "label": "Default",
        "uri": app.config.get("SPIFFWORKFLOW_BACKEND_OPEN_ID_SERVER_URL"),
        "client_id": app.config.get("SPIFFWORKFLOW_BACKEND_OPEN_ID_CLIENT_ID"),
        "client_secret": app.config.get(
            "SPIFFWORKFLOW_BACKEND_OPEN_ID_CLIENT_SECRET_KEY"
        ),
        "additional_valid_client_ids": app.config.get(
            "SPIFFWORKFLOW_BACKEND_OPEN_ID_ADDITIONAL_VALID_CLIENT_IDS"
        ),
    }
]

if app.config.get("ENV", "development") != "production":
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

# Use the SpiffConnector Blueprint, which will auto-discover any
# connector-* packages and provide API endpoints for listing and executing
# available services.
app.register_blueprint(proxy_blueprint)

if __name__ == "__main__":
    app.run(host="localhost", port=7004)
