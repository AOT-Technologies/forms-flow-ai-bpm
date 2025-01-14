from __future__ import annotations
from dataclasses import dataclass

from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.schema import CheckConstraint

from spiffworkflow_backend.models.db import SpiffworkflowBaseDBModel
from spiffworkflow_backend.models.db import db
from spiffworkflow_backend.models.group import GroupModel
from spiffworkflow_backend.models.user import UserModel

import enum
import os
from datetime import datetime

from dataclasses import dataclass
from dataclasses import field
from typing import Any

import marshmallow
from marshmallow import Schema
from marshmallow.decorators import post_load

from spiffworkflow_backend.interfaces import ProcessGroupLite
from spiffworkflow_backend.models.file import File, CONTENT_TYPES

# we only want to save these items to the json file
PROCESS_MODEL_SUPPORTED_KEYS_FOR_DISK_SERIALIZATION = [
    "display_name",
    "description",
    "primary_file_name",
    "primary_process_id",
    "fault_or_suspend_on_exception",
    "exception_notification_addresses",
    "metadata_extraction_paths",
]


class NotificationType(enum.Enum):
    fault = "fault"
    suspend = "suspend"


@dataclass
class ProcessModelInfo(SpiffworkflowBaseDBModel):
    sort_index: str = field(init=False)

    process_id = db.Column(db.Integer, primary_key=True)
    id = db.Column(db.String)
    display_name = db.Column(db.String)
    description= db.Column(db.String)
    is_executable = db.Column(db.Boolean)
    fault_or_suspend_on_exception = db.Column(db.String, default=NotificationType.fault.value)

    process_group=db.Column(db.String, default="formsflow")

    # files: list[File] | None = field(default_factory=list[File])
    content = db.Column(db.LargeBinary)
    type = db.Column(db.String, default="bpmn") # BPMN or DMN

    # just for the API
    # parent_groups: list[ProcessGroupLite] | None = None
    bpmn_version_control_identifier= db.Column(db.String)
    

    @property
    def primary_file_name(self):
        return None

    @property
    def primary_process_id(self):
        return self.id

    @property
    def exception_notification_addresses(self):
        return []

    @property
    def metadata_extraction_paths(self):
        return []

    @property
    def actions(self):
        return {}

    @property
    def display_order(self):
        return 0

    @property
    def files(self):
        file_objects = []
        for content in [self.content]:
            if content:
                file = File(
                    content_type=CONTENT_TYPES.get(self.type, "application/octet-stream"),
                    name=(self.display_name or "bpmn_file") + '.bpmn',
                    type=self.type,
                    last_modified=datetime.now(),  # Placeholder for actual last modified time
                    size=len(content),
                    file_contents=content,
                    process_model_id=self.id,
                )
                file_objects.append(file)
        return file_objects

    @property
    def parent_groups(self):
        return []

    def __post_init__(self) -> None:
        self.sort_index = self.id

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, ProcessModelInfo):
            return False
        if other.id == self.id:
            return True
        return False

    # for use with os.path.join so it can work on windows
    # NOTE: in APIs, ids should always have forward slashes, even in windows.
    # this is because we have to store ids in the database, and we want the same
    # database snapshot to work on any OS.
    def id_for_file_path(self) -> str:
        return self.id.replace("/", os.sep)

    def modified_process_model_identifier(self) -> str:
        return self.modify_process_identifier_for_path_param(self.id)

    @classmethod
    def modify_process_identifier_for_path_param(cls, identifier: str) -> str:
        if "\\" in identifier:
            raise Exception(f"Found backslash in identifier: {identifier}")

        return identifier.replace("/", ":")

    def serialized(self) -> dict[str, Any]:
        file_objects = self.files
        dictionary = {k: v for k, v in self.__dict__.items() if k != "_sa_instance_state" and k != "content"}
        if file_objects is not None:
            serialized_files = []
            for file in file_objects:
                if file is not None:
                    serialized_files.append(file.serialized())
            dictionary["files"] = serialized_files
        return dictionary


class ProcessModelInfoSchema(Schema):
    class Meta:
        model = ProcessModelInfo

    id = marshmallow.fields.String(required=True)
    display_name = marshmallow.fields.String(required=True)
    description = marshmallow.fields.String()
    primary_file_name = marshmallow.fields.String(allow_none=True)
    primary_process_id = marshmallow.fields.String(allow_none=True)
    content = marshmallow.fields.String(allow_none=True)
    type = marshmallow.fields.String(allow_none=True)
    fault_or_suspend_on_exception = marshmallow.fields.String()
    exception_notification_addresses = marshmallow.fields.List(marshmallow.fields.String)
    metadata_extraction_paths = marshmallow.fields.List(
        marshmallow.fields.Dict(
            keys=marshmallow.fields.Str(required=False),
            values=marshmallow.fields.Str(required=False),
            required=False,
        )
    )

    @post_load
    def make_spec(self, data: dict[str, str | bool | int | NotificationType], **_: Any) -> ProcessModelInfo:
        return ProcessModelInfo(**data)  # type: ignore
