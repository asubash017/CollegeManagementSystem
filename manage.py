#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'college_management_system.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc

    # ----  FORCE  MODELS  INTO  REGISTRY  ----
    from django import setup
    setup()

    # 1.  force-import the model file (executes every class)
    import main_app.models               # noqa
    # 2.  trigger signal registration
    import main_app.notification_service # noqa

    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()