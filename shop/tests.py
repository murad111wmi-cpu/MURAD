import io
import uuid
import tempfile
from decimal import Decimal
from django.test import TestCase,Client,override_settings
from django.core.management import call_command
from django.core.exceptions import PermissionDenied,ValidationError
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core import mail
from PIL import Image
from .models import *
from .services import *
from .validators import image_upload

PASSWORD='TestOnly-Strong-Password-482!'
class StoreTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('bootstrap_store',verbosity=0)
        cls.admin=User.objects.create_superuser('admin@example.test',PASSWORD)
        cls.worker=User.objects.create_user('worker@example.test',PASSWORD)
        cls.profile=StaffProfile.objects.create(user=cls.worker,display_name='عامل',assigned_only=False,update_status=True)
        cls.category=Category.objects.create(name_ar='طاولات',name_en='Tables')
        cls.product=Product.objects.create(name_ar='طاولة بلوط',name_en='Oak table',price='100',category=cls.category,featured=True)
        cls.size=ProductOption.objects.create(product=cls.product,kind='size',name_ar='كبير',additional_price='10',width=200,height=100,depth=60)
        cls.color=ProductOption.objects.create(product=cls.product,kind='color',name_ar='بني',color_hex='#795036',additional_price='2')
        cls.wood=ProductOption.objects.create(product=cls.product,kind='wood',name_ar='بلوط',additional_price='5')
        cls.extra=ProductOption.objects.create(product=cls.product,kind='extra',name_ar='درج',additional_price='3')
        cls.branch=Branch.objects.create(name_ar='الفرع',address='عنوان اختبار')
        cls.zone=DeliveryZone.objects.create(name_ar='منطقة',fee='7')
        cls.pickup=FulfillmentMethod.objects.create(name_ar='استلام',kind='pickup')
        cls.delivery=FulfillmentMethod.objects.create(name_ar='توصيل',kind='delivery')
    def data(self): return {'name':'عميل اختبار','phone':'+962790000000','address':'عنوان','notes':'ملاحظة','fulfillment':self.pickup,'branch':self.branch}
    def raw_cart(self): return [{'product':self.product.pk,'quantity':2,'options':[self.size.pk,self.color.pk,self.wood.pk,self.extra.pk]}]
    def make_order(self,**kwargs):
        cart=self.raw_cart();data=self.data();data.update(kwargs)
        return place_order(cart,data,uuid.uuid4(),signed_quote(cart))
    def login_worker(self): self.client.force_login(self.worker)
    def csrf_client(self): return Client(enforce_csrf_checks=True)
    def test_public_home_no_admin_links(self):
        r=self.client.get('/');self.assertEqual(r.status_code,200)
        self.assertNotContains(r,'/admin/');self.assertNotContains(r,'/worker/')
    def test_search_and_category(self):
        r=self.client.get('/products/',{'q':'Oak','category':self.category.pk})
        self.assertContains(r,'طاولة بلوط')
        self.assertNotContains(self.client.get('/products/',{'q':'Missing'}),'طاولة بلوط')
    def test_hidden_category_hides_product(self):
        self.category.active=False;self.category.save()
        self.assertEqual(self.client.get(f'/product/{self.product.pk}/').status_code,404)
        self.assertEqual(self.client.get('/api/catalog/').json()['products'],[])
    def test_options_and_authoritative_prices(self):
        raw=self.raw_cart();raw[0]['price']='0.001';raw[0]['total']='0'
        o,_=place_order(raw,self.data(),uuid.uuid4(),signed_quote(raw))
        self.assertEqual(o.total,Decimal('240'))
        self.assertEqual(o.items.first().options[0]['name_ar'],'كبير')
    def test_other_product_option_rejected(self):
        p=Product.objects.create(name_ar='آخر',price=5)
        opt=ProductOption.objects.create(product=p,name_ar='خطأ',kind='color')
        with self.assertRaises(ValidationError): build_lines([{'product':self.product.pk,'quantity':1,'options':[opt.pk]}])
    def test_duplicate_single_option_rejected(self):
        opt=ProductOption.objects.create(product=self.product,name_ar='آخر',kind='color')
        with self.assertRaises(ValidationError): build_lines([{'product':self.product.pk,'quantity':1,'options':[self.color.pk,opt.pk]}])
    def test_disabled_option_rejected(self):
        self.size.active=False;self.size.save()
        with self.assertRaises(ValidationError): build_lines(self.raw_cart())
    def test_bad_quantity_rejected(self):
        for q in [0,-1,100]:
            with self.assertRaises(ValidationError): build_lines([{'product':self.product.pk,'quantity':q,'options':[]}])
    def test_merged_cart_stock_checked(self):
        self.product.stock_enabled=True;self.product.stock=2;self.product.save()
        with self.assertRaises(ValidationError): build_lines([{'product':self.product.pk,'quantity':2,'options':[]},{'product':self.product.pk,'quantity':1,'options':[self.color.pk]}])
    def test_stock_reduced(self):
        self.product.stock_enabled=True;self.product.stock=4;self.product.save()
        self.make_order();self.product.refresh_from_db();self.assertEqual(self.product.stock,2)
    def test_price_changes_require_review(self):
        raw=self.raw_cart();quote=signed_quote(raw);self.product.price=200;self.product.save()
        with self.assertRaises(ValidationError): place_order(raw,self.data(),uuid.uuid4(),quote)
        self.assertEqual(Order.objects.count(),0)
    def test_currency_change_requires_review(self):
        raw=self.raw_cart();quote=signed_quote(raw);s=StoreSettings.get();s.currency='SAR';s.save()
        with self.assertRaises(ValidationError): place_order(raw,self.data(),uuid.uuid4(),quote)
    def test_forged_quote_rejected(self):
        with self.assertRaises(ValidationError): place_order(self.raw_cart(),self.data(),uuid.uuid4(),'forged')
    def test_request_idempotent(self):
        raw=self.raw_cart();key=uuid.uuid4();q=signed_quote(raw)
        a,ta=place_order(raw,self.data(),key,q);b,tb=place_order(raw,self.data(),key,q)
        self.assertEqual(a.pk,b.pk);self.assertEqual(ta,tb);self.assertEqual(Order.objects.count(),1)
    def test_delivery_fee_from_database(self):
        o,_=self.make_order(fulfillment=self.delivery,zone=self.zone)
        self.assertEqual(o.delivery_fee,7);self.assertEqual(o.total,247)
    def test_delivery_needs_address(self):
        with self.assertRaises(ValidationError): self.make_order(fulfillment=self.delivery,zone=self.zone,address='')
    def test_pickup_branch_product_constraint(self):
        other=Branch.objects.create(name_ar='غير متاح',address='اختبار');self.product.branches.add(other)
        with self.assertRaises(ValidationError): self.make_order()
    def test_customer_orders_aggregated(self):
        a,_=self.make_order();b,_=self.make_order(name='اسم جديد')
        self.assertEqual(Customer.objects.count(),1);self.assertEqual(a.customer_id,b.customer_id)
        self.assertEqual(b.customer_name,'اسم جديد');self.assertEqual(a.customer_name,'عميل اختبار')
    def test_snapshots_survive_catalog_edits(self):
        o,_=self.make_order();self.product.name_ar='تغيير';self.product.price=300;self.product.save();self.color.name_ar='أسود';self.color.save()
        s=StoreSettings.get();s.currency='USD';s.save()
        o.refresh_from_db();self.assertEqual(o.currency,'JOD');self.assertEqual(o.total,240);self.assertEqual(o.items.first().name_ar,'طاولة بلوط')
    def test_tracking_needs_secret(self):
        o,token=self.make_order()
        self.assertIsNone(verify_tracking(o.number,'wrong'));self.assertIsNone(verify_tracking(o.number,''));self.assertEqual(verify_tracking(o.number,token).pk,o.pk)
    def test_tracking_hides_internal_notes_customer_address(self):
        o,token=self.make_order();WorkNote.objects.create(order=o,author=self.admin,text='INTERNAL-SECRET')
        r=self.client.post('/track-order/',{'number':o.number,'token':token})
        self.assertContains(r,o.number);self.assertNotContains(r,'INTERNAL-SECRET');self.assertNotContains(r,o.phone)
    def test_csrf_blocks_public_order_mutations(self):
        c=self.csrf_client()
        self.assertEqual(c.post(f'/product/{self.product.pk}/add/',{'quantity':1}).status_code,403)
        self.assertEqual(c.post('/api/track/',data='{}',content_type='application/json').status_code,403)
    def test_full_customer_flow(self):
        r=self.client.post(f'/product/{self.product.pk}/add/',{'quantity':1,'options':[self.size.pk,self.color.pk,self.wood.pk,self.extra.pk]})
        self.assertEqual(r.status_code,302)
        self.client.post('/cart/',{'index':0,'quantity':2,'action':'update'})
        r=self.client.get('/order/');self.assertEqual(r.status_code,200)
        form=r.context['form'];data={'name':'زبون','phone':'+962790000000','fulfillment':self.pickup.pk,'branch':self.branch.pk,'request_key':form.initial['request_key'],'quote':form.initial['quote']}
        r=self.client.post('/order/',data);self.assertEqual(r.status_code,302)
        o=Order.objects.get();self.assertEqual(o.total,240);r=self.client.get(r.url);self.assertContains(r,o.number)
        self.assertEqual(self.client.session['cart'],[])
    def test_email_login_session_refresh_and_logout(self):
        r=self.client.post('/worker/login/',{'username':'worker@example.test','password':PASSWORD});self.assertEqual(r.status_code,302)
        self.assertEqual(self.client.get('/worker/').status_code,200)
        self.assertEqual(self.client.get('/worker/').status_code,200)
        self.client.post('/logout/');self.assertEqual(self.client.get('/worker/').status_code,302)
    def test_worker_admin_denied(self):
        self.login_worker();r=self.client.get('/admin/');self.assertEqual(r.status_code,302)
        for path in ['/admin/worker-center/','/admin/account/','/admin/shop/storesettings/1/change/']:
            self.assertIn(self.client.get(path).status_code,[302,403])
    def test_worker_settings_post_denied(self):
        self.login_worker();s=StoreSettings.get()
        self.client.post('/admin/shop/storesettings/1/change/',{'currency':'SAR'})
        s.refresh_from_db();self.assertEqual(s.currency,'JOD')
    def test_worker_no_phone_address(self):
        o,_=self.make_order();self.login_worker();r=self.client.get(reverse('work_detail',args=[o.pk]))
        self.assertEqual(r.status_code,200);self.assertNotContains(r,o.phone)
        self.assertNotContains(r,'العنوان:')
    def test_assigned_only_denies_other_orders(self):
        self.profile.assigned_only=True;self.profile.save();o,_=self.make_order();self.login_worker()
        self.assertEqual(self.client.get(reverse('work_detail',args=[o.pk])).status_code,404)
        o.assigned_to=self.worker;o.save();self.assertEqual(self.client.get(reverse('work_detail',args=[o.pk])).status_code,200)
    def test_worker_can_next_stage(self):
        o,_=self.make_order();target=OrderStatus.objects.get(sort_order=1)
        change_status(self.worker,o.pk,target.pk,o.status_id);o.refresh_from_db();self.assertEqual(o.status_id,target.pk);self.assertEqual(o.events.count(),2)
    def test_worker_cannot_skip_or_cancel_or_previous(self):
        o,_=self.make_order()
        for target in [OrderStatus.objects.get(sort_order=3),OrderStatus.objects.get(cancelled=True)]:
            with self.assertRaises(PermissionDenied): change_status(self.worker,o.pk,target.pk,o.status_id)
        change_status(self.worker,o.pk,OrderStatus.objects.get(sort_order=1).pk,o.status_id);o.refresh_from_db()
        with self.assertRaises(PermissionDenied): change_status(self.worker,o.pk,OrderStatus.objects.get(is_initial=True).pk,o.status_id)
    def test_worker_previous_with_permission(self):
        o,_=self.make_order();initial=o.status_id;change_status(self.worker,o.pk,OrderStatus.objects.get(sort_order=1).pk,initial);o.refresh_from_db()
        self.profile.previous_stage=True;self.profile.save();self.worker.refresh_from_db()
        change_status(self.worker,o.pk,initial,o.status_id);o.refresh_from_db();self.assertEqual(o.status_id,initial)
    def test_worker_update_denied_without_permission(self):
        self.profile.update_status=False;self.profile.save();o,_=self.make_order();self.worker.refresh_from_db()
        with self.assertRaises(PermissionDenied): change_status(self.worker,o.pk,OrderStatus.objects.get(sort_order=1).pk,o.status_id)
    def test_concurrent_status_change_rejected(self):
        o,_=self.make_order();old=o.status_id;next_s=OrderStatus.objects.get(sort_order=1)
        change_status(self.admin,o.pk,next_s.pk,old)
        with self.assertRaises(ValidationError): change_status(self.admin,o.pk,OrderStatus.objects.get(sort_order=2).pk,old)
    def test_admin_worker_center_all_operations(self):
        o,_=self.make_order();self.client.force_login(self.admin)
        self.assertEqual(self.client.get('/admin/worker-center/').status_code,200)
        path=reverse('admin_work_detail',args=[o.pk]);self.assertContains(self.client.get(path),o.phone)
        r=self.client.post(path,{'action':'status','status':OrderStatus.objects.get(sort_order=4).pk,'expected':o.status_id});self.assertEqual(r.status_code,302)
        self.client.post(path,{'action':'note','note':'ملاحظة المدير'});self.assertEqual(WorkNote.objects.count(),1)
        self.client.post(path,{'action':'assign','assignee':self.worker.pk});o.refresh_from_db();self.assertEqual(o.assigned_to,self.worker)
    def test_disabled_worker_session_revoked(self):
        self.login_worker();self.profile.active=False;self.profile.save()
        self.assertEqual(self.client.get('/worker/').status_code,302)
    def test_no_order_permission_denied(self):
        self.profile.view_orders=False;self.profile.save();self.login_worker()
        self.assertEqual(self.client.get('/worker/').status_code,403)
    def test_custom_order_private_images_and_permissions(self):
        image=io.BytesIO();Image.new('RGB',(8,8)).save(image,'PNG')
        upload=SimpleUploadedFile('reference.png',image.getvalue(),content_type='image/png')
        with tempfile.TemporaryDirectory() as media,override_settings(MEDIA_ROOT=media):
            r=self.client.get('/custom-order/');key=r.context['form'].initial['request_key']
            r=self.client.post('/custom-order/',{'name':'عميل','phone':'+962790000000','piece':'مكتب','description':'تفاصيل','request_key':key,'images':upload})
            self.assertEqual(r.status_code,302);o=Order.objects.get();self.assertTrue(o.is_custom);self.assertEqual(o.total,0)
            im=o.reference_images.get();self.assertIn(self.client.get(f'/private-image/{im.pk}/').status_code,[302,403])
            self.login_worker();self.assertEqual(self.client.get(reverse('work_detail',args=[o.pk])).status_code,404)
            self.profile.view_custom=True;self.profile.save();self.worker.refresh_from_db();self.assertEqual(self.client.get(f'/private-image/{im.pk}/').status_code,200)
    def test_upload_rejects_svg_and_fake_image(self):
        for filename,data in [('x.svg',b'<svg onload="alert(1)"></svg>'),('x.png',b'not-image')]:
            with self.assertRaises(ValidationError): image_upload(SimpleUploadedFile(filename,data))
    def test_currencies_saved_and_rendered(self):
        s=StoreSettings.get()
        for code in ['JOD','SAR','USD','EUR','JPY']:
            s.currency=code;s.full_clean();s.save()
            self.assertContains(self.client.get(f'/product/{self.product.pk}/'),code)
    def test_storefront_changes_immediate(self):
        s=StoreSettings.get();s.name_ar='متجر جديد';s.primary_color='#123456';s.footer_ar='تذييل جديد';s.save()
        hero=HomepageSection.objects.get(kind='hero');hero.name_ar='عنوان جديد';hero.save()
        r=self.client.get('/');self.assertContains(r,'متجر جديد');self.assertContains(r,'#123456');self.assertContains(r,'تذييل جديد');self.assertContains(r,'عنوان جديد')
        hero.active=False;hero.save();self.assertNotContains(self.client.get('/'),'عنوان جديد')
    def test_display_language_does_not_change_default(self):
        self.client.post('/language/',{'language':'en'});self.assertContains(self.client.get('/'),'lang="en"')
        self.assertEqual(StoreSettings.get().default_language,'ar')
    def test_disabled_language_not_selectable(self):
        s=StoreSettings.get();s.enable_en=False;s.save();self.client.post('/language/',{'language':'en'});self.assertContains(self.client.get('/'),'lang="ar"')
    def test_color_validation(self):
        s=StoreSettings.get();s.primary_color='red;display:none'
        with self.assertRaises(ValidationError): s.full_clean()
    def test_customer_history_protects_product_deletion(self):
        self.make_order()
        from django.db.models.deletion import ProtectedError
        with self.assertRaises(ProtectedError): self.product.delete()
    def test_account_password_change(self):
        self.login_worker();path='/worker/account/';new='Another-Strong-Password-654!'
        r=self.client.post(path,{'action':'password','old_password':PASSWORD,'new_password1':new,'new_password2':new});self.assertEqual(r.status_code,302)
        self.client.post('/logout/');self.assertTrue(self.client.login(email=self.worker.email,password=new))
    def test_account_change_requires_current_password(self):
        self.login_worker();r=self.client.post('/worker/account/',{'action':'profile','email':'hijack@example.test','current_password':'wrong','first_name':'x'})
        self.assertEqual(r.status_code,200);self.worker.refresh_from_db();self.assertEqual(self.worker.email,'worker@example.test')
    @override_settings(EMAIL_HOST='smtp.example.test',DEFAULT_FROM_EMAIL='store@example.test',EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_password_reset_no_enumeration_and_email_sent(self):
        known=self.client.post('/password-reset/',{'email':self.worker.email});unknown=self.client.post('/password-reset/',{'email':'missing@example.test'})
        self.assertEqual(known.status_code,unknown.status_code);self.assertEqual(known.url,unknown.url);self.assertEqual(len(mail.outbox),1)
        self.assertIn('/reset/',mail.outbox[0].body)
    def test_rate_limited_tracking(self):
        for _ in range(20): self.client.post('/track-order/',{'number':'wrong','token':'wrong'})
        self.assertEqual(self.client.post('/track-order/',{'number':'wrong','token':'wrong'}).status_code,403)
    def test_bootstrap_repeatable_without_duplicates(self):
        counts=(OrderStatus.objects.count(),HomepageSection.objects.count(),NavigationItem.objects.count())
        call_command('bootstrap_store',verbosity=0)
        self.assertEqual(counts,(OrderStatus.objects.count(),HomepageSection.objects.count(),NavigationItem.objects.count()))
    def test_admin_pages_and_customer_history(self):
        self.make_order();self.client.force_login(self.admin)
        paths=['/admin/','/admin/shop/product/','/admin/shop/product/add/','/admin/shop/productoption/add/','/admin/shop/user/add/','/admin/shop/storesettings/1/change/','/admin/shop/homepagesection/','/admin/shop/customer/']
        for path in paths: self.assertEqual(self.client.get(path).status_code,200,path)
    def test_orders_paused_and_no_initial_status(self):
        s=StoreSettings.get();s.accepting_orders=False;s.save()
        with self.assertRaises(ValidationError): self.make_order()
        s.accepting_orders=True;s.save();OrderStatus.objects.filter(is_initial=True).update(active=False)
        with self.assertRaises(ValidationError): self.make_order()
    def test_edit_cart_options_without_duplicating_line(self):
        self.client.post(f'/product/{self.product.pk}/add/',{'quantity':2,'options':[self.size.pk]})
        r=self.client.get(f'/product/{self.product.pk}/?edit=0')
        self.assertContains(r,'selected');self.assertEqual(r.context['initial_quantity'],2)
        self.client.post(f'/product/{self.product.pk}/add/',{'quantity':3,'options':[self.color.pk],'edit_index':'0'})
        cart=self.client.session['cart'];self.assertEqual(len(cart),1);self.assertEqual(cart[0]['quantity'],3);self.assertEqual(cart[0]['options'],[self.color.pk])
    def test_valid_png_with_html_extension_rejected(self):
        image=io.BytesIO();Image.new('RGB',(4,4)).save(image,'PNG')
        with self.assertRaises(ValidationError): image_upload(SimpleUploadedFile('attack.html',image.getvalue()))
    def test_email_login_case_insensitive(self):
        self.assertTrue(self.client.login(email='WORKER@EXAMPLE.TEST',password=PASSWORD))
    def test_price_limit_rejected_cleanly(self):
        self.product.price=Decimal('999999999.999');self.product.save()
        with self.assertRaises(ValidationError): build_lines(self.raw_cart())

from django.test import TransactionTestCase
from django.db import connection,connections,close_old_connections
import unittest
@unittest.skipUnless(connection.vendor=='postgresql','Concurrency locking requires PostgreSQL')
class ConcurrentOrdersTests(TransactionTestCase):
    def test_parallel_orders_never_oversell_and_have_unique_numbers(self):
        from concurrent.futures import ThreadPoolExecutor
        call_command('bootstrap_store',verbosity=0)
        p=Product.objects.create(name_ar='مخزون اختبار',price=100,stock_enabled=True,stock=4)
        branch=Branch.objects.create(name_ar='فرع',address='عنوان')
        method=FulfillmentMethod.objects.create(name_ar='استلام',kind='pickup')
        cart=[{'product':p.pk,'quantity':1,'options':[]}]
        quote=signed_quote(cart)
        def submit(i):
            close_old_connections()
            try:
                data={'name':'عميل','phone':f'+96279000000{i}','fulfillment':FulfillmentMethod.objects.get(pk=method.pk),'branch':Branch.objects.get(pk=branch.pk)}
                return place_order(cart,data,uuid.uuid4(),quote)[0].number
            except ValidationError: return None
            finally: connections.close_all()
        with ThreadPoolExecutor(max_workers=6) as executor: results=list(executor.map(submit,range(10)))
        passed=[x for x in results if x]
        self.assertEqual(len(passed),4);self.assertEqual(len(set(passed)),4);self.assertEqual(Order.objects.count(),4)
        p.refresh_from_db();self.assertEqual(p.stock,0)
