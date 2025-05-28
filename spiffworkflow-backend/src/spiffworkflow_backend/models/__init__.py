from flask import g
from sqlalchemy import event
from sqlalchemy.orm import with_loader_criteria
from sqlalchemy.orm import Mapper
from spiffworkflow_backend.config.default import config_from_env
from spiffworkflow_backend.exceptions.error import NotAuthorizedError
from spiffworkflow_backend.models.db import db
from spiffworkflow_backend.models.task import TaskModel
from spiffworkflow_backend.routes.authentication_controller import _get_decoded_token

import inspect
import traceback


@event.listens_for(db.session, "do_orm_execute")
def filter_by_tenant_key(execute_state, *args, **kwargs):
    """Intercepts `select` queries
    and add filter criteria tenant_key = <logged in user's tenant_key>
    """
    statement = execute_state.statement
    model = execute_state.bind_mapper.entity

    has_tenant_key = hasattr(model, "tenant_key")
    if has_tenant_key and config_from_env("MULTI_TENANCY_ENABLED", default=False):
        if getattr(g, "token", None) is not None:
            decoded_token = _get_decoded_token(g.token)
            execute_state.statement = statement.options(
                with_loader_criteria(
                    model,
                    model.tenant_key == decoded_token["tenantKey"],
                    include_aliases=True,
                )
            )


@event.listens_for(Mapper, "before_insert", retval=True)
@event.listens_for(Mapper, "before_update", retval=True)
@event.listens_for(Mapper, "before_delete")
def permission_check_and_set_tenant_key(mapper, connection, target):
    """Intercepts `insert/update/delete operations
    For insert/update:
        - Sets the tenant_key attribute if applicable
        - Checks if logged in user is from same tenant as the object
    For delete:
        - Checks if logged in user is from same tenant as the object

    Raises:
        NotAuthorizedError: Raised if the logged in user is not from same tenant as of the object
    """
    has_tenant_key = hasattr(target, "tenant_key")
    if has_tenant_key and config_from_env("MULTI_TENANCY_ENABLED", default=False):
        if getattr(g, "token", None) is not None:
            decoded_token = _get_decoded_token(g.token)
            if target.tenant_key and target.tenant_key != decoded_token["tenantKey"]:
                raise NotAuthorizedError(
                    f"User {g.user.username} is not authorized to \
                        perform requested action on <{target.__class__.name}: {target.id}>"
                )
            elif target.tenant_key is None:
                target.tenant_key = decoded_token["tenantKey"]
