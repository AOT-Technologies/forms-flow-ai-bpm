from typing import Dict, TypedDict, Optional, List


class ApplicationData(TypedDict, total=False):
    applicationId: int
    applicationStatus: str
    submitterLastName: str
    submitterFirstName: str
    submitterEmail: str
    currentUser: str
    currentUserRole: str  # JSON string
    formUrl: str
    webFormUrl: str
    formName: str
    submitterName: str
    submissionDate: str
    tenantKey: str
    formId: str
    skipReview: bool


class TaskData(TypedDict):
    data: ApplicationData


class UpdateTaskDataPayload(TypedDict):
    new_task_data: TaskData


class ApplicationAuditPayload(TypedDict):
    applicationStatus: str
    formUrl: str
    color: Optional[str]
    percentage: Optional[float]
    submittedBy: str


class ApplicationStatePayload(TypedDict):
    applicationStatus: str
    formUrl: str
    isResubmit: bool
    eventName: Optional[str]
    submittedBy: str


class PatchSubmissionItem(TypedDict):
    op: str
    path: str
    value: str
