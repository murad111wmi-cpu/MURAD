from django.core.management.base import BaseCommand
from django.db import transaction
from shop.models import *
class Command(BaseCommand):
    help='Initialize editable store defaults, without sample products, contacts or accounts.'
    @transaction.atomic
    def handle(self,*args,**options):
        StoreSettings.get()
        if not OrderStatus.objects.exists():
            statuses=[('جديد','New','#8b6b4e'),('مؤكد','Confirmed','#557c72'),('قيد التنفيذ','In progress','#b17f42'),('جاهز','Ready','#3b7554'),('خرج للتوصيل','Out for delivery','#477295'),('مكتمل','Completed','#356c44'),('ملغى','Cancelled','#a34c4c')]
            for i,(ar,en,color) in enumerate(statuses): OrderStatus.objects.create(name_ar=ar,name_en=en,color=color,sort_order=i,is_initial=i==0,terminal=i in [5,6],cancelled=i==6)
        if not NavigationItem.objects.exists():
            for i,(ar,en,url) in enumerate([('الرئيسية','Home','/'),('المجموعة','Collection','/products/'),('تفصيل خاص','Bespoke','/custom-order/'),('تتبع طلبك','Track order','/track-order/')]): NavigationItem.objects.create(name_ar=ar,name_en=en,url=url,sort_order=i)
        if not HomepageSection.objects.exists():
            hero=HomepageSection.objects.create(kind='hero',name_ar='أثاث وأعمال خشبية بتفاصيل تصنع الفرق.',name_en='Considered details. Timeless living.',body_ar='اختر قطعة جاهزة، أو خصّص المقاس والخشب واللون. نصنع ما يشبهك.',body_en='Choose a ready piece or personalise the size, wood and finish. Made to feel like you.',sort_order=0)
            SectionButton.objects.create(section=hero,name_ar='استعرض المجموعة',name_en='Explore the collection',url='/products/')
            SectionButton.objects.create(section=hero,name_ar='طلب تفصيل خاص',name_en='Create a bespoke piece',url='/custom-order/',sort_order=1)
            for i,(kind,ar,en,bodyar,bodyen) in enumerate([('categories','قطعة لكل مساحة','A piece for every space','',''),('featured','اختيارات دار الخشب','Selected pieces','',''),('custom','من فكرة، إلى قطعة تعيش معك.','From an idea to a piece of your home.','أرسل تفاصيل القطعة التي تتخيلها، وسنتواصل معك لمناقشة التصميم والسعر.','Tell us what you have in mind. We will contact you to discuss the design and quote.'),('branches','زرنا في فروعنا','Visit our workshops','',''),('contact','لنتحدث عن مساحتك','Let’s talk about your space','','')],1):
                section=HomepageSection.objects.create(kind=kind,name_ar=ar,name_en=en,body_ar=bodyar,body_en=bodyen,sort_order=i)
                if kind=='custom': SectionButton.objects.create(section=section,name_ar='ابدأ طلبك',name_en='Start your request',url='/custom-order/')
        # Fulfillment needs actual business branches/zones before activation.
        self.stdout.write(self.style.SUCCESS('Store defaults initialized. No sample inventory or account created.'))
