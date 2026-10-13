import io
import tempfile
from django.test import TestCase,Client,override_settings
from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from .models import User,Category,StoreSettings

TOKEN='test-only-setup-token-with-more-than-32-chars'
PASSWORD='Test-Only-Password-Complex-7492!'
@override_settings(STORE_SETUP_TOKEN=TOKEN)
class DeploymentTests(TestCase):
    def setUp(self): call_command('bootstrap_store',verbosity=0)
    def payload(self):
        return {'email':'owner@example.test','first_name':'صاحب المحل','password1':PASSWORD,'password2':PASSWORD,'setup_code':TOKEN}
    @override_settings(STORE_SETUP_TOKEN='')
    def test_setup_disabled_without_configuration(self):
        self.assertEqual(self.client.get('/setup/').status_code,404)
    def test_setup_requires_correct_token(self):
        data=self.payload();data['setup_code']='wrong'
        r=self.client.post('/setup/',data)
        self.assertEqual(r.status_code,200);self.assertEqual(User.objects.count(),0)
        self.assertNotContains(r,TOKEN)
    def test_first_admin_created_and_setup_permanently_closes(self):
        r=self.client.post('/setup/',self.payload())
        self.assertEqual(r.status_code,302);self.assertEqual(r.url,'/admin/')
        u=User.objects.get();self.assertTrue(u.is_superuser);self.assertTrue(u.is_staff);self.assertTrue(u.check_password(PASSWORD))
        self.assertEqual(self.client.get('/admin/').status_code,200)
        self.assertEqual(self.client.get('/setup/').status_code,404)
        u.is_active=False;u.save()
        self.assertEqual(self.client.get('/setup/').status_code,404)
    def test_non_ascii_setup_token_rejected(self):
        data=self.payload();data['setup_code']='رمز غير صحيح'
        self.assertEqual(self.client.post('/setup/',data).status_code,200)
        self.assertEqual(User.objects.count(),0)
    def test_setup_password_policy_enforced(self):
        data=self.payload();data['password1']=data['password2']='123'
        self.assertEqual(self.client.post('/setup/',data).status_code,200)
        self.assertEqual(User.objects.count(),0)
    def test_csrf_required_for_setup(self):
        self.assertEqual(Client(enforce_csrf_checks=True).post('/setup/',self.payload()).status_code,403)
    def test_setup_rate_limited(self):
        data=self.payload();data['setup_code']='incorrect'
        for _ in range(5): self.client.post('/setup/',data)
        self.assertEqual(self.client.post('/setup/',data).status_code,403)
    @override_settings(SERVE_PUBLIC_UPLOADS=True)
    def test_raster_public_image_serving_and_private_path_rejected(self):
        with tempfile.TemporaryDirectory() as folder,override_settings(MEDIA_ROOT=folder):
            image=io.BytesIO();Image.new('RGB',(4,4)).save(image,'PNG')
            category=Category.objects.create(name_ar='اختبار')
            category.image.save('photo.png',SimpleUploadedFile('photo.png',image.getvalue()),save=True)
            from .views import public_upload
            from django.test import RequestFactory
            filename=category.image.name.split('/')[-1]
            r=public_upload(RequestFactory().get('/'),filename)
            self.assertEqual(r.status_code,200);self.assertEqual(r['Content-Type'],'image/png');r.file_to_stream.close()  # RequestFactory does not run the HTTP request lifecycle.
            from django.http import Http404
            for name in ['../private/custom/photo.png','bad.html','missing.png','..']:
                with self.assertRaises(Http404): public_upload(RequestFactory().get('/'),name)
    @override_settings(SERVE_PUBLIC_UPLOADS=False)
    def test_public_upload_disabled_by_default(self):
        from .views import public_upload
        from django.http import Http404
        from django.test import RequestFactory
        with self.assertRaises(Http404): public_upload(RequestFactory().get('/'),'a'*32+'.png')
