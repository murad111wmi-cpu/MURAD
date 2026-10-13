import os
import unittest
import tempfile
from pathlib import Path
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.core.management import call_command
from .models import *
from .tests import PASSWORD

@unittest.skipUnless(os.environ.get('RUN_BROWSER_TESTS')=='1','Set RUN_BROWSER_TESTS=1 for Chromium end-to-end tests')
class BrowserJourney(StaticLiveServerTestCase):
    def setUp(self):
        from playwright.sync_api import sync_playwright
        from unittest.mock import patch
        # Playwright's synchronous API runs a loop in this test thread only.
        self.async_guard=patch.dict(os.environ,{'DJANGO_ALLOW_ASYNC_UNSAFE':'true'});self.async_guard.start()
        self.media=tempfile.TemporaryDirectory();self.override=override_settings(MEDIA_ROOT=self.media.name,DEBUG=True);self.override.enable()
        call_command('bootstrap_store',verbosity=0)
        self.admin=User.objects.create_superuser('owner@example.test',PASSWORD)
        self.worker=User.objects.create_user('maker@example.test',PASSWORD)
        StaffProfile.objects.create(user=self.worker,display_name='الصانع',assigned_only=False,update_status=True,previous_stage=True)
        self.branch=Branch.objects.create(name_ar='فرع اختبار',address='عنوان اختبار')
        self.pickup=FulfillmentMethod.objects.create(name_ar='استلام من الفرع',kind='pickup')
        self.pw=sync_playwright().start();self.browser=self.pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        self.context=self.browser.new_context(viewport={'width':1440,'height':1000})
        self.page=self.context.new_page();self.errors=[]
        self.page.on('pageerror',lambda error:self.errors.append(str(error)))
    def tearDown(self):
        self.browser.close();self.pw.stop();self.override.disable();self.media.cleanup();self.async_guard.stop()
    def go(self,path): self.page.goto(self.live_server_url+path)
    def test_full_shop_admin_customer_worker_journey(self):
        from playwright.sync_api import expect
        self.go('/admin/login/');self.page.locator('#id_username').fill(self.admin.email);self.page.locator('#id_password').fill(PASSWORD);self.page.locator('input[type=submit]').click();expect(self.page).to_have_url(self.live_server_url+'/admin/')
        self.go('/admin/shop/category/add/');self.page.locator('#id_name_ar').fill('طاولات');self.page.locator('#id_name_en').fill('Tables');self.page.locator('input[name=_save]').click();expect(self.page).to_have_url(self.live_server_url+'/admin/shop/category/')
        category=Category.objects.get(name_ar='طاولات')
        self.go('/admin/shop/product/add/');self.page.locator('#id_name_ar').fill('طاولة حقيقية للاختبار');self.page.locator('#id_name_en').fill('Real test table');self.page.locator('#id_price').fill('100');self.page.locator('#id_category').select_option(str(category.pk));self.page.locator('#id_featured').check();self.page.locator('input[name=_save]').click();expect(self.page).to_have_url(self.live_server_url+'/admin/shop/product/')
        product=Product.objects.get(name_ar='طاولة حقيقية للاختبار')
        for kind,ar,price in [('size','كبير','10'),('size','صغير','0'),('color','بني','2'),('color','أسود','1'),('wood','بلوط','5'),('extra','درج','3')]:
            self.go('/admin/shop/productoption/add/');self.page.locator('#id_product').select_option(str(product.pk));self.page.locator('#id_kind').select_option(kind);self.page.locator('#id_name_ar').fill(ar);self.page.locator('#id_additional_price').fill(price);self.page.locator('input[name=_save]').click();expect(self.page).to_have_url(self.live_server_url+'/admin/shop/productoption/')
        import io
        from PIL import Image
        image=io.BytesIO();Image.new('RGB',(400,300),'#795036').save(image,'PNG')
        self.go('/admin/shop/productimage/add/');self.page.locator('#id_product').select_option(str(product.pk));self.page.locator('#id_image').set_input_files({'name':'table.png','mimeType':'image/png','buffer':image.getvalue()});self.page.locator('#id_is_main').check();self.page.locator('input[name=_save]').click();expect(self.page).to_have_url(self.live_server_url+'/admin/shop/productimage/')
        # Edit business content through the real admin form.
        self.go('/admin/shop/storesettings/1/change/');self.page.locator('#id_name_ar').fill('دار الخشب للاختبار');self.page.locator('#id_primary_color').fill('#123456');self.page.locator('#id_footer_ar').fill('تذييل اختباري');self.page.locator('#id_logo').set_input_files({'name':'logo.png','mimeType':'image/png','buffer':image.getvalue()});self.page.locator('input[name=_save]').click();expect(self.page).to_have_url(self.live_server_url+'/admin/shop/storesettings/')
        self.go('/');expect(self.page.locator('.brand')).to_contain_text('دار الخشب للاختبار');expect(self.page.locator('footer')).to_contain_text('تذييل اختباري');self.assertEqual(self.page.locator('.brand img').evaluate('(el)=>el.naturalWidth'),400)
        # Anonymous mobile customer.
        customer=self.browser.new_context(viewport={'width':390,'height':844});p=customer.new_page();p.on('pageerror',lambda e:self.errors.append(str(e)));p.goto(self.live_server_url+'/products/');p.locator('#q').fill('حقيقية');p.locator('.filter-bar button').click();p.locator('.product-info h3 a').click();expect(p.locator('h1')).to_have_text('طاولة حقيقية للاختبار')
        options={o.name_ar:o for o in product.options.all()}
        for o in [options['كبير'],options['بني'],options['بلوط']]:
            p.locator(f'select[name=options]:has(option[value="{o.pk}"])').select_option(str(o.pk))
        p.locator(f'input[name=options][value="{options["درج"].pk}"]').check();p.locator('.purchase-row button').click();expect(p).to_have_url(self.live_server_url+'/cart/')
        p.locator('input[name=quantity]').fill('2');p.locator('button[value=update]').click();p.wait_for_load_state();
        self.assertEqual(p.locator('a[href="/order/"]').count(),1,p.locator('body').inner_text()[:6000])
        p.locator('a[href="/order/"]').click();p.locator('#id_name').fill('زبون المتصفح');p.locator('#id_phone').fill('+962790000000');p.locator('#id_fulfillment').select_option(str(self.pickup.pk));p.locator('#id_branch').select_option(str(self.branch.pk));p.locator('#checkout-form button[type=submit]').click();expect(p.locator('h1')).to_contain_text('وصلنا طلبك');order=Order.objects.get();self.assertEqual(order.total,240);token=p.locator('.tracking-secret code').inner_text()
        # Check mobile page does not overflow.
        self.assertTrue(p.evaluate('document.documentElement.scrollWidth <= window.innerWidth'))
        # Worker signs in and advances two stages, then reverses one.
        work_context=self.browser.new_context(viewport={'width':390,'height':844});w=work_context.new_page();w.on('pageerror',lambda e:self.errors.append(str(e)));w.goto(self.live_server_url+'/worker/login/');w.locator('#id_username').fill(self.worker.email);w.locator('#id_password').fill(PASSWORD);w.locator('button[type=submit]').click();expect(w).to_have_url(self.live_server_url+'/worker/');w.locator('.work-card').click();w.locator('button',has_text='المرحلة التالية').click();w.locator('button',has_text='المرحلة التالية').click();w.locator('button',has_text='المرحلة السابقة').click();order.refresh_from_db();self.assertEqual(order.status.sort_order,1);self.assertTrue(w.evaluate('document.documentElement.scrollWidth <= window.innerWidth'))
        p.goto(self.live_server_url+'/track-order/');p.locator('#number').fill(order.number);p.locator('#token').fill(token);p.locator('button[type=submit]').click();expect(p.locator('.order-overview .status')).to_have_text('مؤكد')
        # Administrator uses the same worker operations without impersonation.
        self.go(f'/admin/worker-center/{order.pk}/');self.page.locator('button',has_text='المرحلة التالية').click();order.refresh_from_db();self.assertEqual(order.status.sort_order,2)
        # Change currency through the real admin form, while preserving old orders.
        for currency in ['SAR','USD','EUR','JOD']:
            self.go('/admin/shop/storesettings/1/change/')
            search=self.page.locator('input[aria-label="ابحث عن عملة / Search currency"]');search.fill('Euro')
            self.assertFalse(self.page.locator('#id_currency option[value=EUR]').evaluate('(el)=>el.hidden'))
            search.fill('');self.page.locator('#id_currency').select_option(currency)
            self.page.locator('input[name=_save]').click();expect(self.page).to_have_url(self.live_server_url+'/admin/shop/storesettings/')
            self.assertEqual(StoreSettings.get().currency,currency);order.refresh_from_db();self.assertEqual(order.currency,'JOD');self.assertEqual(order.total,240)
        # English presentation, persisted display selection.
        p.goto(self.live_server_url+'/');p.locator('.language').click();expect(p.locator('html')).to_have_attribute('lang','en');expect(p.locator('html')).to_have_attribute('dir','ltr');p.reload();expect(p.locator('html')).to_have_attribute('lang','en')
        self.assertEqual(self.errors,[])
        customer.close();work_context.close()
