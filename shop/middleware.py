from django.contrib.auth import logout
class ActiveStaffMiddleware:
    def __init__(self,get_response): self.get_response=get_response
    def __call__(self,request):
        if request.user.is_authenticated and not request.user.is_superuser:
            profile = getattr(request.user,'profile',None)
            if not request.user.is_active or not profile or not profile.active:
                logout(request)
        return self.get_response(request)
