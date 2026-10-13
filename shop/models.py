import uuid
from decimal import Decimal
from django.db import models
from django.db.models import Q
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import MinValueValidator, RegexValidator
from .validators import hex_color, image_upload

NONNEG = MinValueValidator(Decimal('0'))

def upload_path(instance,filename):
    suffix = filename.rsplit('.',1)[-1].lower()
    return f'images/{uuid.uuid4().hex}.{suffix}'

class UserManager(BaseUserManager):
    use_in_migrations = True
    def get_by_natural_key(self,email): return self.get(email__iexact=email)
    def create_user(self,email,password=None,**extra):
        if not email: raise ValueError('Email required')
        user = self.model(email=self.normalize_email(email).lower(),**extra)
        user.set_password(password)
        user.save(using=self._db)
        return user
    def create_superuser(self,email,password=None,**extra):
        extra.update(is_staff=True,is_superuser=True)
        return self.create_user(email,password,**extra)

class User(AbstractUser):
    username = None
    email = models.EmailField('البريد الإلكتروني',unique=True)
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    objects = UserManager()
    def __str__(self): return self.get_full_name() or self.email

class StaffProfile(models.Model):
    user = models.OneToOneField(User,on_delete=models.CASCADE,related_name='profile')
    display_name = models.CharField('الاسم الظاهر',max_length=120)
    active = models.BooleanField('فعال',default=True)
    view_orders = models.BooleanField('مشاهدة الطلبات',default=True)
    update_status = models.BooleanField('تغيير الحالة',default=False)
    previous_stage = models.BooleanField('الرجوع لمرحلة سابقة',default=False)
    view_phone = models.BooleanField('مشاهدة الهاتف',default=False)
    view_address = models.BooleanField('مشاهدة العنوان',default=False)
    view_custom = models.BooleanField('مشاهدة طلبات التفصيل',default=False)
    add_notes = models.BooleanField('إضافة ملاحظات داخلية',default=False)
    assigned_only = models.BooleanField('طلباته المسندة فقط',default=True)
    def __str__(self): return self.display_name
    class Meta: verbose_name='عامل وصلاحياته'; verbose_name_plural='العمال والصلاحيات'

class Named(models.Model):
    name_ar = models.CharField('الاسم بالعربية',max_length=160)
    name_en = models.CharField('الاسم بالإنجليزية',max_length=160,blank=True)
    active = models.BooleanField('فعال',default=True)
    sort_order = models.PositiveIntegerField('الترتيب',default=0)
    class Meta: abstract=True; ordering=['sort_order','pk']
    def __str__(self): return self.name_ar
    def label(self,lang): return self.name_en if lang=='en' and self.name_en else self.name_ar

class StoreSettings(models.Model):
    name_ar = models.CharField('اسم المتجر بالعربية',max_length=160,default='دار الخشب')
    name_en = models.CharField('اسم المتجر بالإنجليزية',max_length=160,default='DAR AL KHASHAB')
    description_ar = models.TextField('وصف المتجر بالعربية',blank=True)
    description_en = models.TextField('وصف المتجر بالإنجليزية',blank=True)
    logo = models.ImageField('الشعار',upload_to=upload_path,blank=True,validators=[image_upload])
    favicon = models.ImageField('أيقونة الموقع',upload_to=upload_path,blank=True,validators=[image_upload])
    default_language = models.CharField('اللغة الافتراضية',max_length=2,choices=[('ar','العربية'),('en','English')],default='ar')
    enable_ar = models.BooleanField('تفعيل العربية',default=True)
    enable_en = models.BooleanField('تفعيل الإنجليزية',default=True)
    language_switch = models.BooleanField('إظهار تبديل لغة العرض للزبون',default=True)
    currency = models.CharField('العملة الأساسية',max_length=3,default='JOD')
    primary_color = models.CharField('اللون الرئيسي',max_length=7,default='#493124',validators=[hex_color])
    secondary_color = models.CharField('اللون الثانوي',max_length=7,default='#8b6b4e',validators=[hex_color])
    background_color = models.CharField('الخلفية',max_length=7,default='#f8f5ef',validators=[hex_color])
    text_color = models.CharField('النص',max_length=7,default='#2f2823',validators=[hex_color])
    accent_color = models.CharField('لون الإبراز',max_length=7,default='#c5a379',validators=[hex_color])
    header_color = models.CharField('خلفية الرأس',max_length=7,default='#f8f5ef',validators=[hex_color])
    footer_color = models.CharField('خلفية التذييل',max_length=7,default='#493124',validators=[hex_color])
    button_color = models.CharField('الأزرار',max_length=7,default='#493124',validators=[hex_color])
    footer_ar = models.TextField('نص التذييل بالعربية',default='صُنع بعناية. ليبقى معك.')
    footer_en = models.TextField('نص التذييل بالإنجليزية',default='Thoughtfully crafted. Made to stay.')
    collection_title_ar = models.CharField('عنوان صفحة المنتجات بالعربية',max_length=200,default='قطع تكمّل حكاية بيتك.')
    collection_title_en = models.CharField('عنوان صفحة المنتجات بالإنجليزية',max_length=200,default='Pieces for the story of your home.')
    custom_title_ar = models.CharField('عنوان التفصيل بالعربية',max_length=200,default='أخبرنا عن قطعتك.')
    custom_title_en = models.CharField('عنوان التفصيل بالإنجليزية',max_length=200,default='Tell us about your piece.')
    custom_intro_ar = models.TextField('مقدمة التفصيل بالعربية',default='أرسل فكرتك والمقاسات والصور المرجعية. سنتواصل معك لمناقشة التصميم والسعر.')
    custom_intro_en = models.TextField('مقدمة التفصيل بالإنجليزية',default='Share your vision, dimensions and reference photos. We will contact you to discuss design and price.')
    tagline_ar = models.CharField('سطر الهوية بالعربية',max_length=200,default='حرفة. تفاصيل. حياة.')
    tagline_en = models.CharField('سطر الهوية بالإنجليزية',max_length=200,default='CRAFT. DETAIL. LIFE.')
    receipt_message_ar = models.TextField('رسالة استلام الطلب بالعربية',default='تم استلام طلبك بنجاح وسيتم التواصل معك لتأكيد الطلب.')
    receipt_message_en = models.TextField('رسالة استلام الطلب بالإنجليزية',default='We received your request and will contact you to confirm it.')
    phone = models.CharField('الهاتف',max_length=40,blank=True)
    whatsapp = models.CharField('واتساب (مع رمز الدولة)',max_length=40,blank=True)
    email = models.EmailField('بريد التواصل',blank=True)
    address = models.TextField('العنوان',blank=True)
    order_prefix = models.CharField('بادئة رقم الطلب',max_length=12,default='DK',validators=[RegexValidator(r'^[A-Z0-9-]+$')])
    address_mode = models.CharField('العنوان',max_length=10,choices=[('required','مطلوب'),('optional','اختياري'),('hidden','مخفي')],default='optional')
    notes_mode = models.CharField('الملاحظات',max_length=10,choices=[('required','مطلوب'),('optional','اختياري'),('hidden','مخفي')],default='optional')
    accepting_orders = models.BooleanField('استقبال الطلبات',default=True)
    accepting_custom = models.BooleanField('استقبال طلبات التفصيل',default=True)
    def clean(self):
        from django.core.exceptions import ValidationError
        from .currencies import CURRENCIES
        if not self.enable_ar and not self.enable_en: raise ValidationError('يجب تفعيل لغة واحدة على الأقل')
        if not getattr(self,f'enable_{self.default_language}',False): raise ValidationError('يجب تفعيل اللغة الافتراضية')
        if self.currency not in CURRENCIES: raise ValidationError('اختر عملة رسمية مدعومة')
        if self.pk != 1: raise ValidationError('يوجد إعداد عام واحد فقط')
    def save(self,*args,**kwargs): self.pk=1; super().save(*args,**kwargs)
    @classmethod
    def get(cls): return cls.objects.get_or_create(pk=1)[0]
    def __str__(self): return self.name_ar
    class Meta: verbose_name='إعدادات المتجر'; verbose_name_plural='إعدادات المتجر'

class Category(Named):
    description_ar = models.TextField('الوصف بالعربية',blank=True)
    description_en = models.TextField('الوصف بالإنجليزية',blank=True)
    image = models.ImageField('الصورة',upload_to=upload_path,blank=True,validators=[image_upload])
    class Meta(Named.Meta): verbose_name='تصنيف'; verbose_name_plural='التصنيفات'

class Branch(Named):
    address = models.TextField('العنوان')
    phone = models.CharField('الهاتف',max_length=40,blank=True)
    whatsapp = models.CharField('واتساب',max_length=40,blank=True)
    location_url = models.URLField('رابط الموقع',blank=True)
    class Meta(Named.Meta): verbose_name='فرع'; verbose_name_plural='الفروع'

class BranchHours(models.Model):
    branch = models.ForeignKey(Branch,on_delete=models.CASCADE,related_name='hours')
    day = models.PositiveSmallIntegerField('اليوم',choices=list(enumerate(['الاثنين','الثلاثاء','الأربعاء','الخميس','الجمعة','السبت','الأحد'])))
    closed = models.BooleanField('مغلق',default=False)
    opens = models.TimeField('يفتح',null=True,blank=True)
    closes = models.TimeField('يغلق',null=True,blank=True)
    class Meta:
        ordering=['day']
        constraints=[models.UniqueConstraint(fields=['branch','day'],name='unique_branch_day')]

class DeliveryZone(Named):
    def clean(self):
        from .currencies import validate_amount
        if self.fee is not None: validate_amount(self.fee)
    fee = models.DecimalField('رسوم التوصيل بالعملة الحالية',max_digits=12,decimal_places=3,validators=[NONNEG])
    class Meta(Named.Meta): verbose_name='منطقة توصيل'; verbose_name_plural='مناطق التوصيل'

class FulfillmentMethod(Named):
    kind = models.CharField('النوع',max_length=10,choices=[('delivery','توصيل'),('pickup','استلام من فرع')])
    class Meta(Named.Meta): verbose_name='طريقة استلام'; verbose_name_plural='طرق الاستلام'

class Product(Named):
    def clean(self):
        from .currencies import validate_amount
        if self.price is not None: validate_amount(self.price)
    sku = models.CharField('SKU',max_length=60,blank=True)
    description_ar = models.TextField('الوصف بالعربية',blank=True)
    description_en = models.TextField('الوصف بالإنجليزية',blank=True)
    price = models.DecimalField('السعر بالعملة الحالية',max_digits=12,decimal_places=3,validators=[NONNEG])
    category = models.ForeignKey(Category,on_delete=models.PROTECT,related_name='products',null=True,blank=True,verbose_name='التصنيف')
    branches = models.ManyToManyField(Branch,blank=True,verbose_name='الفروع')
    featured = models.BooleanField('منتج مميز',default=False)
    available = models.BooleanField('متاح للطلب',default=True)
    stock_enabled = models.BooleanField('تفعيل المخزون',default=False)
    stock = models.PositiveIntegerField('المخزون',default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    @property
    def main_image(self): return self.images.order_by('-is_main','sort_order','id').first()
    class Meta(Named.Meta): verbose_name='منتج'; verbose_name_plural='المنتجات'

class ProductImage(models.Model):
    product = models.ForeignKey(Product,on_delete=models.CASCADE,related_name='images')
    image = models.ImageField('الصورة',upload_to=upload_path,validators=[image_upload])
    alt = models.CharField('وصف الصورة',max_length=160,blank=True)
    is_main = models.BooleanField('صورة رئيسية',default=False)
    sort_order = models.PositiveIntegerField('الترتيب',default=0)
    class Meta: ordering=['sort_order','id']
    def save(self,*args,**kwargs):
        super().save(*args,**kwargs)
        if self.is_main: type(self).objects.filter(product=self.product).exclude(pk=self.pk).update(is_main=False)

class ProductOption(Named):
    def clean(self):
        from .currencies import validate_amount
        if self.additional_price is not None: validate_amount(self.additional_price)
    product = models.ForeignKey(Product,on_delete=models.CASCADE,related_name='options')
    kind = models.CharField('نوع الخيار',max_length=20,choices=[('size','مقاس'),('color','لون'),('wood','خشب'),('extra','إضافة'),('other','خيار آخر')])
    description_ar = models.TextField('الوصف بالعربية',blank=True)
    description_en = models.TextField('الوصف بالإنجليزية',blank=True)
    additional_price = models.DecimalField('السعر الإضافي',max_digits=12,decimal_places=3,default=0,validators=[NONNEG])
    color_hex = models.CharField('اللون',max_length=7,blank=True,validators=[hex_color])
    image = models.ImageField('صورة اختيارية',upload_to=upload_path,blank=True,validators=[image_upload])
    width = models.DecimalField('العرض',max_digits=8,decimal_places=2,null=True,blank=True,validators=[NONNEG])
    height = models.DecimalField('الارتفاع',max_digits=8,decimal_places=2,null=True,blank=True,validators=[NONNEG])
    depth = models.DecimalField('العمق',max_digits=8,decimal_places=2,null=True,blank=True,validators=[NONNEG])
    unit = models.CharField('الوحدة',max_length=10,default='cm')
    class Meta(Named.Meta): verbose_name='خيار منتج'; verbose_name_plural='خيارات المنتجات'

class OrderStatus(Named):
    color = models.CharField('لون الحالة',max_length=7,default='#8b6b4e',validators=[hex_color])
    is_initial = models.BooleanField('حالة البداية',default=False)
    terminal = models.BooleanField('حالة نهائية',default=False)
    cancelled = models.BooleanField('حالة إلغاء',default=False)
    class Meta(Named.Meta):
        verbose_name='حالة طلب'; verbose_name_plural='حالات الطلب'
        constraints=[models.UniqueConstraint(fields=['is_initial'],condition=Q(is_initial=True),name='single_initial_status')]

class Customer(models.Model):
    name = models.CharField('الاسم',max_length=160)
    phone = models.CharField('الهاتف',max_length=40,unique=True)
    address = models.TextField('العنوان',blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return self.name
    class Meta: verbose_name='عميل'; verbose_name_plural='العملاء'

class DailyOrderCounter(models.Model):
    day = models.DateField(unique=True)
    value = models.PositiveIntegerField(default=0)

class Order(models.Model):
    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    number = models.CharField('رقم الطلب',max_length=50,unique=True)
    tracking_hash = models.CharField(max_length=64,editable=False)
    request_key = models.UUIDField(unique=True,editable=False)
    customer = models.ForeignKey(Customer,on_delete=models.PROTECT,related_name='orders')
    customer_name = models.CharField('الاسم وقت الطلب',max_length=160)
    phone = models.CharField('الهاتف وقت الطلب',max_length=40)
    address = models.TextField('العنوان وقت الطلب',blank=True)
    zone = models.ForeignKey(DeliveryZone,on_delete=models.PROTECT,null=True,blank=True)
    branch = models.ForeignKey(Branch,on_delete=models.PROTECT,null=True,blank=True)
    fulfillment = models.ForeignKey(FulfillmentMethod,on_delete=models.PROTECT,null=True,blank=True)
    fulfillment_label = models.CharField(max_length=160,blank=True)
    currency = models.CharField('عملة الطلب',max_length=3)
    subtotal = models.DecimalField('المجموع الفرعي',max_digits=18,decimal_places=3,validators=[NONNEG])
    delivery_fee = models.DecimalField('التوصيل',max_digits=12,decimal_places=3,default=0)
    total = models.DecimalField('الإجمالي',max_digits=18,decimal_places=3,validators=[NONNEG])
    status = models.ForeignKey(OrderStatus,on_delete=models.PROTECT,verbose_name='الحالة')
    notes = models.TextField('ملاحظات العميل',blank=True)
    assigned_to = models.ForeignKey(User,on_delete=models.SET_NULL,null=True,blank=True,related_name='assigned_orders',verbose_name='العامل')
    is_custom = models.BooleanField('طلب تفصيل',default=False)
    custom_details = models.JSONField(default=dict,blank=True)
    created_at = models.DateTimeField('التاريخ',auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta: ordering=['-created_at']; verbose_name='طلب'; verbose_name_plural='الطلبات'
    def __str__(self): return self.number

class OrderItem(models.Model):
    order = models.ForeignKey(Order,on_delete=models.CASCADE,related_name='items')
    product = models.ForeignKey(Product,on_delete=models.PROTECT)
    name_ar = models.CharField(max_length=160)
    name_en = models.CharField(max_length=160,blank=True)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=12,decimal_places=3)
    options = models.JSONField(default=list)
    line_total = models.DecimalField(max_digits=14,decimal_places=3)
    class Meta: constraints=[models.CheckConstraint(condition=Q(quantity__gte=1),name='positive_quantity')]

class OrderEvent(models.Model):
    order = models.ForeignKey(Order,on_delete=models.CASCADE,related_name='events')
    status = models.ForeignKey(OrderStatus,on_delete=models.PROTECT)
    actor = models.ForeignKey(User,on_delete=models.SET_NULL,null=True,blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta: ordering=['created_at','pk']

class WorkNote(models.Model):
    order = models.ForeignKey(Order,on_delete=models.CASCADE,related_name='work_notes')
    author = models.ForeignKey(User,on_delete=models.SET_NULL,null=True)
    text = models.TextField('ملاحظة داخلية',max_length=3000)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta: ordering=['created_at']

class CustomOrderImage(models.Model):
    order = models.ForeignKey(Order,on_delete=models.CASCADE,related_name='reference_images')
    image = models.ImageField(upload_to='private/custom/',validators=[image_upload])

class HomepageSection(Named):
    kind = models.CharField('نوع القسم',max_length=20,choices=[('hero','واجهة'),('featured','منتجات مميزة'),('categories','تصنيفات'),('custom','طلب تفصيل'),('about','من نحن'),('branches','فروع'),('contact','تواصل')])
    body_ar = models.TextField('النص بالعربية',blank=True)
    body_en = models.TextField('النص بالإنجليزية',blank=True)
    image = models.ImageField('الصورة',upload_to=upload_path,blank=True,validators=[image_upload])
    background_color = models.CharField('الخلفية',max_length=7,blank=True,validators=[hex_color])
    class Meta(Named.Meta): verbose_name='قسم واجهة'; verbose_name_plural='أقسام الواجهة'

class SectionButton(Named):
    section = models.ForeignKey(HomepageSection,on_delete=models.CASCADE,related_name='buttons')
    url = models.CharField('الرابط',max_length=300)
    def clean(self):
        from django.core.exceptions import ValidationError
        from urllib.parse import urlparse
        if not (self.url.startswith('/') and not self.url.startswith('//')) and urlparse(self.url).scheme != 'https':
            raise ValidationError('استخدم مسارًا محليًا أو رابط HTTPS')

class NavigationItem(Named):
    url = models.CharField('المسار المحلي',max_length=300,validators=[RegexValidator(r'^/(?!/)[A-Za-z0-9/_?#=\-]*$')])
    class Meta(Named.Meta): verbose_name='عنصر قائمة'; verbose_name_plural='قائمة المتجر'

class SocialLink(Named):
    url = models.URLField('الرابط')
    class Meta(Named.Meta): verbose_name='رابط تواصل'; verbose_name_plural='روابط التواصل'

class AbuseBucket(models.Model):
    key = models.CharField(max_length=64,unique=True)
    count = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(db_index=True)
