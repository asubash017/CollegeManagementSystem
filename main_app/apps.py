# main_app/apps.py
from django.apps import AppConfig


class MainAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'main_app'

    def ready(self):
        # Import models **after** registry is ready
        try:
            from . import models               # noqa: F401
            from . import notification_service # noqa: F401
        except ImportError:
            # If circular import happens, import lazily
            from django.utils.module_loading import import_string
            import_string('main_app.models')
            import_string('main_app.notification_service')