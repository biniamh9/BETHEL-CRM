from django.conf import settings


def church(request):
    return {"church": settings.CHURCH}
