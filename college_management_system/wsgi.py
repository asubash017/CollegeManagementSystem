"""
WSGI config for college_management_system project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/3.1/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'college_management_system.settings')

application = get_wsgi_application()

# ----  FORCE  MODELS  INTO  REGISTRY  ----
import main_app.models               # noqa
import main_app.notification_service # noqa