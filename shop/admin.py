from django.contrib import admin,messages
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm
from django import forms
from django.urls import path,reverse
from django.shortcuts import redirect
from django.db.models import Count
from django.core.exceptions import PermissionDenied
from .models import *
from .forms import StaffCreationForm,StaffChangeForm,EmailLoginForm
from .currencies import CURRENCIES,PREFERRED
from .security import rate_limit

class ShopAdminSite(admin.AdminSite):
    site_header='دار الخشب | مركز التحكم'
    site_title='دار الخشب'
    index_title='إدارة المتجر'
    login_form=EmailLoginForm
    def has_permission(self,request): return request.user.is_active and request.user.is_superuser
    def login(self,request,extra_context=None):
        if request.method=='POST':
            from .security import digest
            rate_limit(request,'login-ip',30,900)
            rate_limit(request,'login-account',10,900,identity=digest(request.POST.get('username','').lower()))
        return super().login(request,extra_context)
    def index(self,request,extra_context=None):
        ctx={'order_counts':OrderStatus.objects.annotate(order_count=Count('order')).order_by('sort_order'),'product_count':Product.objects.count(),'customer_count':Customer.objects.count(),'worker_count':StaffProfile.objects.filter(active=True).count(),'recent_orders':Order.objects.select_related('status')[:8]}
        ctx.update(extra_context or {})
        return super().index(request,ctx)
site=ShopAdminSite(name='admin')

class ProtectedAdmin(admin.ModelAdmin):
    actions=['archive_selected']
    @admin.action(description='تعطيل / أرشفة العناصر المختارة')
    def archive_selected(self,request,queryset): queryset.update(active=False)
    def get_actions(self,request):
        actions=super().get_actions(request); actions.pop('delete_selected',None); return actions

class NamedAdmin(ProtectedAdmin):
    list_display=['name_ar','name_en','active','sort_order']
    list_filter=['active']
    search_fields=['name_ar','name_en']
    list_editable=['active','sort_order']

class StaffInline(admin.StackedInline):
    model=StaffProfile; extra=0; max_num=1

@admin.register(User,site=site)
class ShopUserAdmin(UserAdmin):
    add_form=StaffCreationForm
    form=StaffChangeForm
    list_display=['email','first_name','is_active','is_superuser']
    ordering=['email']; search_fields=['email','first_name','last_name']; list_filter=['is_active','is_superuser']
    fieldsets=[(None,{'fields':['email','password']}),('بيانات الحساب',{'fields':['first_name','last_name','is_active','is_staff','is_superuser']})]
    add_fieldsets=[('حساب جديد',{'classes':['wide'],'fields':['email','first_name','last_name','password1','password2']})]
    inlines=[StaffInline]
    filter_horizontal=[]
    def get_actions(self,request):
        actions=super().get_actions(request); actions.pop('delete_selected',None); return actions
    def save_model(self,request,obj,form,change):
        if obj.pk==request.user.pk and (not obj.is_active or not obj.is_superuser):
            raise PermissionDenied('لا يمكنك تعطيل حسابك الإداري الحالي')
        if obj.is_superuser: obj.is_staff=True
        super().save_model(request,obj,form,change)
    def save_related(self,request,form,formsets,change):
        super().save_related(request,form,formsets,change)
        user=form.instance
        if not user.is_superuser: StaffProfile.objects.get_or_create(user=user,defaults={'display_name':user.get_full_name() or user.email})

@admin.register(StaffProfile,site=site)
class StaffAdmin(admin.ModelAdmin):
    list_display=['display_name','user','active','assigned_only','update_status']
    list_filter=['active']; search_fields=['display_name','user__email']
    def get_queryset(self,request): return super().get_queryset(request).select_related('user')

class ImageInline(admin.TabularInline): model=ProductImage; extra=0
class OptionInline(admin.StackedInline): model=ProductOption; extra=0
@admin.register(Product,site=site)
class ProductAdmin(NamedAdmin):
    list_display=['name_ar','price','category','active','available','featured','sort_order']
    list_editable=['active','available','featured','sort_order']
    list_filter=['active','category','featured','available']
    filter_horizontal=['branches']
    inlines=[ImageInline,OptionInline]
    fieldsets=[('المنتج',{'fields':['name_ar','name_en','sku','description_ar','description_en','category','price']}),('الظهور والتوفر',{'fields':['active','available','featured','sort_order','branches','stock_enabled','stock']})]
    actions=['archive_selected','duplicate_product']
    @admin.action(description='نسخ المنتج المحدد مع خياراته (غير منشور)')
    def duplicate_product(self,request,queryset):
        for old in queryset:
            branches=list(old.branches.all()); options=list(old.options.all()); images=list(old.images.all())
            old.pk=None; old.name_ar+=' — نسخة'; old.active=False; old.sku=''; old.save(); old.branches.set(branches)
            for o in options: o.pk=None; o.product=old; o.save()
            for im in images: im.pk=None; im.product=old; im.save()

@admin.register(ProductOption,site=site)
class OptionAdmin(NamedAdmin):
    list_display=['name_ar','product','kind','additional_price','active','sort_order']
    list_filter=['kind','active','product']; search_fields=['name_ar','name_en','product__name_ar']

class HoursInline(admin.TabularInline): model=BranchHours; extra=0
@admin.register(Branch,site=site)
class BranchAdmin(NamedAdmin): inlines=[HoursInline]

class ButtonInline(admin.TabularInline): model=SectionButton; extra=0
@admin.register(HomepageSection,site=site)
class SectionAdmin(NamedAdmin):
    inlines=[ButtonInline]
    list_display=['name_ar','kind','active','sort_order']

for model in [Category,DeliveryZone,FulfillmentMethod,NavigationItem,SocialLink]: site.register(model,NamedAdmin)
@admin.register(OrderStatus,site=site)
class StatusAdmin(NamedAdmin):
    list_display=['name_ar','active','sort_order','is_initial','terminal','cancelled']

class SettingsForm(forms.ModelForm):
    currency=forms.ChoiceField(label='العملة الأساسية',choices=[('العملات المفضلة',[(c,c) for c in PREFERRED]),('جميع العملات',[(c,c) for c in CURRENCIES])],help_text='تغيير العملة لا يحول الأسعار. حدّث أسعار المنتجات والتوصيل بعد التغيير. الطلبات القديمة تحتفظ بعملتها.')
    class Meta:
        model=StoreSettings; fields='__all__'
        help_texts={'address_mode':'الإخفاء يطبق على الاستلام من الفرع. يظهر العنوان ويُطلب عند اختيار التوصيل.'}
        widgets={f:forms.TextInput(attrs={'type':'color'}) for f in ['primary_color','secondary_color','background_color','text_color','accent_color','header_color','footer_color','button_color']}
    class Media: js=['shop/admin.js']; css={'all':['shop/admin.css']}

@admin.register(StoreSettings,site=site)
class SettingsAdmin(admin.ModelAdmin):
    form=SettingsForm
    fieldsets=[('عام',{'fields':['name_ar','name_en','description_ar','description_en','accepting_orders','accepting_custom']}),('الهوية والألوان',{'fields':['logo','favicon','primary_color','secondary_color','background_color','text_color','accent_color','header_color','footer_color','button_color']}),('اللغات والعملة',{'fields':['default_language','enable_ar','enable_en','language_switch','currency']}),('التواصل والتذييل',{'fields':['phone','whatsapp','email','address','footer_ar','footer_en']}),('نصوص الصفحات',{'fields':['collection_title_ar','collection_title_en','custom_title_ar','custom_title_en','custom_intro_ar','custom_intro_en','tagline_ar','tagline_en','receipt_message_ar','receipt_message_en']}),('الطلبات',{'fields':['order_prefix','address_mode','notes_mode']})]
    def has_add_permission(self,request): return not StoreSettings.objects.exists()
    def has_delete_permission(self,request,obj=None): return False
    def save_model(self,request,obj,form,change):
        if change and 'currency' in form.changed_data: messages.warning(request,'تم تغيير العملة دون تحويل الأسعار. حدّث أسعار المنتجات ورسوم التوصيل؛ الطلبات السابقة محفوظة بعملتها الأصلية.')
        super().save_model(request,obj,form,change)

class ItemInline(admin.TabularInline):
    model=OrderItem; extra=0; can_delete=False
    readonly_fields=['product','name_ar','name_en','quantity','unit_price','options','line_total']
    def has_add_permission(self,request,obj=None): return False
class EventInline(admin.TabularInline):
    model=OrderEvent; extra=0; can_delete=False
    readonly_fields=['status','actor','created_at']
    def has_add_permission(self,request,obj=None): return False
@admin.register(Order,site=site)
class OrderAdmin(admin.ModelAdmin):
    list_display=['number','customer_name','status','total','currency','is_custom','assigned_to','created_at']
    list_filter=['status','is_custom','currency','assigned_to']; search_fields=['number','customer_name','phone']
    readonly_fields=['number','customer_name','phone','address','fulfillment_label','currency','subtotal','delivery_fee','total','status','notes','is_custom','custom_details','created_at','updated_at']
    fields=readonly_fields+['assigned_to']
    inlines=[ItemInline,EventInline]
    actions=None
    def has_add_permission(self,request): return False
    def has_delete_permission(self,request,obj=None): return False
    def formfield_for_foreignkey(self,db_field,request,**kwargs):
        if db_field.name=='assigned_to': kwargs['queryset']=User.objects.filter(is_active=True,profile__active=True)
        return super().formfield_for_foreignkey(db_field,request,**kwargs)

@admin.register(Customer,site=site)
class CustomerAdmin(admin.ModelAdmin):
    list_display=['name','phone','order_count','latest_order']; search_fields=['name','phone']
    readonly_fields=['name','phone','address','created_at','order_count','latest_order','customer_orders']; fields=readonly_fields
    def get_queryset(self,request): return super().get_queryset(request).prefetch_related('orders')
    def order_count(self,obj): return obj.orders.count()
    order_count.short_description='عدد الطلبات'
    def latest_order(self,obj):
        o=obj.orders.first(); return o.created_at if o else '—'
    latest_order.short_description='آخر طلب'
    def customer_orders(self,obj):
        from django.utils.html import format_html_join
        return format_html_join('', '<p><a href="{}">{}</a> — {}</p>',((reverse('admin:shop_order_change',args=[o.pk]),o.number,str(o.total)+' '+o.currency) for o in obj.orders.all()))
    customer_orders.short_description='الطلبات'
    def has_add_permission(self,request): return False
    def has_delete_permission(self,request,obj=None): return False
@admin.register(ProductImage,site=site)
class ProductImageAdmin(admin.ModelAdmin):
    list_display=['product','alt','is_main','sort_order']
    list_filter=['product']; search_fields=['product__name_ar','alt']
