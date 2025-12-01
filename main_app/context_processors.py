from .models import SystemSettings

def system_settings(request):
    setting = SystemSettings.objects.first()
    if not setting:
        return {'system_settings': None}
    return {'system_settings': setting}
