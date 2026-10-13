from collections import Counter
from decimal import Decimal
import uuid
import hmac
from django.db import transaction
from django.db.models import F
from django.core.exceptions import ValidationError, PermissionDenied
from django.core import signing
from django.utils import timezone
from .models import *
from .security import digest, tracking_token, can, is_admin

def visible_products():
    return Product.objects.filter(active=True).filter(Q(category__active=True)|Q(category__isnull=True))

def build_lines(cart,locked=False):
    if not isinstance(cart,list) or len(cart)>50: raise ValidationError('السلة غير صالحة')
    lines=[]
    totals=Counter()
    qs=visible_products()
    if locked: qs=qs.select_for_update(of=('self',))
    products={p.pk:p for p in qs.filter(pk__in=[x.get('product') for x in cart if isinstance(x,dict)]).prefetch_related('options','images')}
    for raw in cart:
        if not isinstance(raw,dict): raise ValidationError('السلة غير صالحة')
        try:
            p=products[int(raw['product'])]
            qty=int(raw['quantity'])
            ids=raw.get('options',[])
            if not isinstance(ids,list) or len(ids)>30: raise ValueError()
            ids=list(dict.fromkeys(int(i) for i in ids))
        except (KeyError,ValueError,TypeError): raise ValidationError('أحد المنتجات لم يعد متاحًا')
        if qty<1 or qty>99 or not p.available: raise ValidationError('الكمية أو توفر المنتج غير صالح')
        options=list(p.options.filter(active=True,pk__in=ids))
        if len(options)!=len(ids): raise ValidationError('خيار غير متاح أو لا يتبع المنتج')
        kinds=Counter(o.kind for o in options)
        if any(kinds[k]>1 for k in ['size','color','wood','other']): raise ValidationError('اختر قيمة واحدة لكل نوع خيار')
        price=p.price+sum((o.additional_price for o in options),Decimal('0'))
        from .currencies import validate_amount
        validate_amount(price)
        if price < 0 or price > Decimal('999999999.999'): raise ValidationError('سعر الخيارات يتجاوز الحد المسموح')
        totals[p.pk]+=qty
        lines.append({'product':p,'quantity':qty,'options':options,'price':price,'total':price*qty})
    for pk,qty in totals.items():
        if products[pk].stock_enabled and products[pk].stock<qty: raise ValidationError('الكمية المطلوبة تتجاوز المخزون')
    return lines

def quote_data(cart):
    s=StoreSettings.get()
    lines=build_lines(cart)
    return {'currency':s.currency,'cart': [{'product':l['product'].pk,'quantity':l['quantity'],'options':sorted(o.pk for o in l['options']),'price':str(l['price'])} for l in lines], 'zones':[(z.pk,str(z.fee)) for z in DeliveryZone.objects.filter(active=True).order_by('pk')]}

def signed_quote(cart): return signing.dumps(quote_data(cart),salt='checkout')

def check_quote(cart,quote):
    try: old=signing.loads(quote,salt='checkout',max_age=3600)
    except signing.BadSignature: raise ValidationError('انتهت مراجعة الأسعار؛ افتح السلة من جديد')
    # JSON converts tuples to lists.
    import json
    current=json.loads(json.dumps(quote_data(cart)))
    if old!=current: raise ValidationError('تغير السعر أو العملة أو التوصيل؛ راجع الأسعار ثم أرسل مجددًا')

@transaction.atomic
def place_order(cart,cleaned,key,quote=None,custom=None):
    s=StoreSettings.objects.select_for_update().get(pk=1)
    existing=Order.objects.filter(request_key=key).first()
    if existing: return existing,tracking_token(key)
    if custom is None:
        if not s.accepting_orders: raise ValidationError('استقبال الطلبات متوقف مؤقتًا')
        if not cart: raise ValidationError('السلة فارغة')
        lines=build_lines(cart,locked=True)
        check_quote(cart,quote)
    else:
        if not s.accepting_custom: raise ValidationError('طلبات التفصيل متوقفة مؤقتًا')
        lines=[]
    status=OrderStatus.objects.filter(active=True,is_initial=True,cancelled=False).first()
    if not status: raise ValidationError('الطلب غير متاح الآن؛ لم يضبط المتجر حالة البداية')
    fee=Decimal('0'); zone=None; branch=None; method=None
    if custom is None:
        method=cleaned.get('fulfillment')
        if not method or not FulfillmentMethod.objects.filter(pk=method.pk,active=True).exists(): raise ValidationError('اختر طريقة استلام متاحة')
        if method.kind=='delivery':
            zone=cleaned.get('zone')
            if not zone or not DeliveryZone.objects.filter(pk=zone.pk,active=True).exists(): raise ValidationError('اختر منطقة التوصيل')
            zone=DeliveryZone.objects.select_for_update().get(pk=zone.pk)
            fee=zone.fee
            from .currencies import validate_amount
            validate_amount(fee)
            if not cleaned.get('address'): raise ValidationError('أدخل عنوان التوصيل')
        else:
            branch=cleaned.get('branch')
            if not branch or not Branch.objects.filter(pk=branch.pk,active=True).exists(): raise ValidationError('اختر فرع الاستلام')
            if any(l['product'].branches.exists() and not l['product'].branches.filter(pk=branch.pk,active=True).exists() for l in lines):
                raise ValidationError('أحد المنتجات غير متاح في فرع الاستلام المحدد')
    day=timezone.localdate()
    counter,_=DailyOrderCounter.objects.get_or_create(day=day)
    counter=DailyOrderCounter.objects.select_for_update().get(pk=counter.pk)
    counter.value+=1; counter.save(update_fields=['value'])
    number=f'{s.order_prefix}-{day:%Y%m%d}-{counter.value:04d}'
    customer,_=Customer.objects.get_or_create(phone=cleaned['phone'],defaults={'name':cleaned['name'],'address':cleaned.get('address','')})
    subtotal=sum((l['total'] for l in lines),Decimal('0'))
    token=tracking_token(key)
    order=Order.objects.create(number=number,tracking_hash=digest(token),request_key=key,customer=customer,customer_name=cleaned['name'],phone=cleaned['phone'],address=cleaned.get('address',''),zone=zone,branch=branch,fulfillment=method,fulfillment_label=str(method or ''),currency=s.currency,subtotal=subtotal,delivery_fee=fee,total=subtotal+fee,status=status,notes=cleaned.get('notes',''),is_custom=custom is not None,custom_details=custom or {})
    for l in lines:
        OrderItem.objects.create(order=order,product=l['product'],name_ar=l['product'].name_ar,name_en=l['product'].name_en,quantity=l['quantity'],unit_price=l['price'],line_total=l['total'],options=[{'id':o.pk,'kind':o.kind,'name_ar':o.name_ar,'name_en':o.name_en,'additional_price':str(o.additional_price),'width':str(o.width or ''),'height':str(o.height or ''),'depth':str(o.depth or ''),'unit':o.unit} for o in l['options']])
        if l['product'].stock_enabled: Product.objects.filter(pk=l['product'].pk).update(stock=F('stock')-l['quantity'])
    OrderEvent.objects.create(order=order,status=status)
    return order,token

def worker_orders(user):
    if not can(user,'view_orders'): raise PermissionDenied()
    qs=Order.objects.select_related('status','assigned_to').prefetch_related('items','events__status','reference_images')
    if not is_admin(user):
        if not can(user,'view_custom'): qs=qs.filter(is_custom=False)
        if user.profile.assigned_only: qs=qs.filter(assigned_to=user)
    return qs

@transaction.atomic
def change_status(user,order_id,target_id,expected):
    if not can(user,'update_status'): raise PermissionDenied()
    order=worker_orders(user).select_for_update(of=('self',)).get(pk=order_id)
    if str(order.status_id)!=str(expected): raise ValidationError('حدث تعديل آخر؛ حدّث الصفحة أولًا')
    try: target=OrderStatus.objects.get(pk=target_id,active=True)
    except OrderStatus.DoesNotExist: raise ValidationError('الحالة غير متاحة')
    workflow=list(OrderStatus.objects.filter(active=True,cancelled=False).values_list('pk',flat=True))
    old_index=workflow.index(order.status_id) if order.status_id in workflow else -1
    new_index=workflow.index(target.pk) if target.pk in workflow else -1
    if not is_admin(user):
        if order.status.terminal or target.cancelled or (new_index not in [old_index-1,old_index+1]) or new_index<0:
            raise PermissionDenied('يسمح للعامل بالانتقال خطوة واحدة فقط')
        if new_index<old_index and not can(user,'previous_stage'): raise PermissionDenied()
    if target.pk==order.status_id: return order
    order.status=target; order.save(update_fields=['status','updated_at'])
    OrderEvent.objects.create(order=order,status=target,actor=user)
    return order

def verify_tracking(number,token):
    order=Order.objects.select_related('status').prefetch_related('items','events__status').filter(number=number).first()
    if not order or not hmac.compare_digest(order.tracking_hash,digest(token)): return None
    return order
