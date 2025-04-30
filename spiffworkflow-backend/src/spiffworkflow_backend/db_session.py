from flask import g
from flask_sqlalchemy.session import Session

from spiffworkflow_backend.config.default import config_from_env


class CustomSession(Session):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def bulk_save_objects(self, objects, *args, **kwargs):
        from spiffworkflow_backend.routes.authentication_controller import _get_decoded_token

        if config_from_env("MULTI_TENANCY_ENABLED", default=False) and getattr(g, 'token', None) is not None:
            decoded_token = _get_decoded_token(g.token)
            for object in objects:
                has_tenant_key = hasattr(object, "tenant_key")
                if has_tenant_key and decoded_token and object.tenant_key is None:
                    object.tenant_key = decoded_token["tenantKey"]
                # object.tenant_key = self.process_instance.tenant_key
        return super().bulk_save_objects(objects, *args, **kwargs)
