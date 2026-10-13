from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.utils import timezone
from shop.models import AbuseBucket
class Command(BaseCommand):
    help='Remove expired sessions and rate-limit windows; no store records are deleted.'
    def handle(self,*args,**kwargs):
        call_command('clearsessions')
        count,_=AbuseBucket.objects.filter(expires_at__lt=timezone.now()).delete()
        self.stdout.write(f'Expired rate windows removed: {count}')
