import hashlib
import hmac
import time
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.core.exceptions import PermissionDenied
from .models import AbuseBucket

def digest(value): return hashlib.sha256(value.encode()).hexdigest()
def tracking_token(key): return hmac.new(settings.SECRET_KEY.encode(),str(key).encode(),hashlib.sha256).hexdigest()
def rate_limit(request,scope,limit=20,seconds=600,identity=None):
    ip = request.META.get('REMOTE_ADDR','unknown')
    if getattr(settings,'SECURE_PROXY_SSL_HEADER',None):
        ip = request.META.get('HTTP_X_REAL_IP',ip)
    value = identity or ip
    key = hmac.new(settings.SECRET_KEY.encode(),f'{scope}:{value}:{int(time.time())//seconds}'.encode(),hashlib.sha256).hexdigest()
    with transaction.atomic():
        bucket,_=AbuseBucket.objects.get_or_create(key=key,defaults={'expires_at':timezone.now()+timedelta(seconds=seconds*2)})
        bucket=AbuseBucket.objects.select_for_update().get(pk=bucket.pk)
        if bucket.count >= limit: raise PermissionDenied('محاولات كثيرة. حاول لاحقًا.')
        AbuseBucket.objects.filter(pk=bucket.pk).update(count=F('count')+1)

def is_admin(user): return user.is_authenticated and user.is_active and user.is_superuser

def can(user,permission):
    if is_admin(user): return True
    profile=getattr(user,'profile',None)
    return bool(user.is_authenticated and user.is_active and profile and profile.active and getattr(profile,permission,False))
