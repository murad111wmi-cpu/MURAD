import uuid
import json
from functools import wraps
from django.shortcuts import render,redirect,get_object_or_404
from django.http import JsonResponse,HttpResponse,HttpResponseBadRequest,FileResponse
from django.views.decorators.http import require_POST,require_GET
from django.contrib.auth import logout,update_session_auth_hash,login
from django.contrib.auth.views import LoginView,PasswordResetView
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from django.core.exceptions import ValidationError,PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from .models import *
from .forms import *
from .services import *
from .security import *

def private(response):
    response['Cache-Control']='no-store'
    response['Referrer-Policy']='same-origin'
    return response

def staff_required(view):
    @wraps(view)
    def wrapper(request,*args,**kwargs):
        if not request.user.is_authenticated: return redirect('/worker/login/?next='+request.path)
        if not is_admin(request.user) and not getattr(request.user,'profile',None): raise PermissionDenied()
        return view(request,*args,**kwargs)
    return wrapper

def home(request):
    return render(request,'shop/home.html',{'sections':HomepageSection.objects.filter(active=True).prefetch_related('buttons'),'featured':visible_products().filter(featured=True).prefetch_related('images')[:8],'categories':Category.objects.filter(active=True),'branches':Branch.objects.filter(active=True).prefetch_related('hours')})

def products(request):
    qs=visible_products().prefetch_related('images','category')
    q=request.GET.get('q','')[:120]
    if q: qs=qs.filter(Q(name_ar__icontains=q)|Q(name_en__icontains=q)|Q(description_ar__icontains=q)|Q(description_en__icontains=q))
    category=request.GET.get('category','')
    if category.isdigit(): qs=qs.filter(category_id=int(category))
    return render(request,'shop/products.html',{'page':Paginator(qs,24).get_page(request.GET.get('page')),'categories':Category.objects.filter(active=True),'q':q,'selected_category':category})

def product(request,pk):
    p=get_object_or_404(visible_products().prefetch_related('images','options','branches'),pk=pk)
    groups=[(k,label,list(p.options.filter(kind=k,active=True))) for k,label in ProductOption._meta.get_field('kind').choices]
    edit=request.GET.get('edit','')
    initial=None
    raw=request.session.get('cart',[])
    if edit.isdigit() and int(edit)<len(raw) and raw[int(edit)]['product']==pk: initial=raw[int(edit)]
    return render(request,'shop/product.html',{'product':p,'groups':groups,'selected_options':initial['options'] if initial else [],'initial_quantity':initial['quantity'] if initial else 1,'edit_index':edit if initial else ''})

@require_POST
def language(request):
    s=StoreSettings.get(); lang=request.POST.get('language')
    if s.language_switch and lang in ['ar','en'] and getattr(s,f'enable_{lang}',False): request.session['display_language']=lang
    return redirect('/')

@require_POST
def add_cart(request,pk):
    rate_limit(request,'cart',100)
    cart=list(request.session.get('cart',[]))
    try:
        ids=[int(x) for x in request.POST.getlist('options') if x]
        qty=int(request.POST.get('quantity',1))
        row={'product':pk,'quantity':qty,'options':sorted(set(ids))}
        build_lines([row])
        edit=request.POST.get('edit_index','')
        if edit:
            if not edit.isdigit() or int(edit)>=len(cart) or cart[int(edit)]['product']!=pk: raise ValidationError('السطر غير صالح')
            cart.pop(int(edit))
        if len(cart)>=50: raise ValidationError('السلة ممتلئة')
        existing=next((x for x in cart if x['product']==pk and x['options']==row['options']),None)
        if existing: existing['quantity']+=qty
        else: cart.append(row)
        build_lines(cart)
        request.session['cart']=cart
        messages.success(request,'أضيف المنتج للسلة / Added to cart')
    except (ValidationError,ValueError,TypeError) as e: messages.error(request,str(e))
    return redirect('/cart/')

def cart(request):
    raw=list(request.session.get('cart',[]))
    if request.method=='POST':
        try:
            index=int(request.POST.get('index','-1'))
            if not 0<=index<len(raw): raise ValueError()
            if request.POST.get('action')=='remove': raw.pop(index)
            else: raw[index]['quantity']=int(request.POST.get('quantity',1))
            build_lines(raw)
            request.session['cart']=raw
        except (ValueError,ValidationError) as e: messages.error(request,str(e))
        return redirect('/cart/')
    try:
        lines=build_lines(raw)
    except ValidationError as e:
        lines=[]; messages.error(request,'تعذر تسعير بعض العناصر؛ احذفها من السلة ثم أعد إضافتها. '+str(e))
    return private(render(request,'shop/cart.html',{'lines':lines,'raw_cart':raw,'subtotal':sum((l['total'] for l in lines),Decimal('0'))}))

@require_POST
def clear_cart(request):
    request.session['cart']=[]
    return redirect('/cart/')

def checkout(request):
    s=StoreSettings.get()
    if not s.accepting_orders: return render(request,'shop/unavailable.html',status=503)
    raw=request.session.get('cart',[])
    if not raw: return redirect('/cart/')
    key=request.session.get('checkout_key')
    if not key:
        key=str(uuid.uuid4()); request.session['checkout_key']=key
    try: lines=build_lines(raw)
    except ValidationError as e: messages.error(request,str(e)); return redirect('/cart/')
    quote=signed_quote(raw)
    form=CheckoutForm(request.POST or None,initial={'request_key':key,'quote':quote})
    if request.method=='POST':
        rate_limit(request,'orders',12,3600)
        if form.is_valid():
            if str(form.cleaned_data['request_key'])!=key: raise PermissionDenied()
            try:
                order,token=place_order(raw,form.cleaned_data,uuid.UUID(key),form.cleaned_data['quote'])
                remember_order(request,order,token)
                request.session['cart']=[]; request.session.pop('checkout_key',None)
                return redirect('receipt',number=order.number)
            except ValidationError as e: form.add_error(None,e)
    zones=[{'id':z.pk,'fee':str(z.fee)} for z in DeliveryZone.objects.filter(active=True)]
    methods=[{'id':m.pk,'kind':m.kind} for m in FulfillmentMethod.objects.filter(active=True)]
    return private(render(request,'shop/checkout.html',{'form':form,'lines':lines,'subtotal':sum((l['total'] for l in lines),Decimal('0')),'zones_data':zones,'methods_data':methods}))

def remember_order(request,order,token):
    seen=request.session.get('receipts',{})
    seen[order.number]=token
    request.session['receipts']=dict(list(seen.items())[-10:])

def receipt(request,number):
    token=request.session.get('receipts',{}).get(number,'')
    order=verify_tracking(number,token)
    if not order: raise PermissionDenied()
    return private(render(request,'shop/receipt.html',{'order':order,'tracking_token':token}))

def track(request):
    order=None
    if request.method=='POST':
        rate_limit(request,'tracking',20,600)
        number=request.POST.get('number','').strip()[:50]
        token=request.POST.get('token','').strip()[:128]
        order=verify_tracking(number,token)
        if not order: messages.error(request,'رقم الطلب أو رمز التتبع غير صحيح / Incorrect number or tracking code')
    return private(render(request,'shop/track.html',{'order':order}))

def custom_order(request):
    if not StoreSettings.get().accepting_custom: return render(request,'shop/unavailable.html',status=503)
    key=request.session.get('custom_key')
    if not key: key=str(uuid.uuid4()); request.session['custom_key']=key
    form=CustomOrderForm(request.POST or None,request.FILES or None,initial={'request_key':key})
    if request.method=='POST':
        rate_limit(request,'custom-orders',6,3600)
        if form.is_valid():
            if str(form.cleaned_data['request_key'])!=key: raise PermissionDenied()
            try:
                details={k:form.cleaned_data[k] for k in ['piece','description','dimensions','color','wood']}
                with transaction.atomic():
                    order,token=place_order([],form.cleaned_data,uuid.UUID(key),custom=details)
                    if not order.reference_images.exists():
                        for f in form.cleaned_data['images']: CustomOrderImage.objects.create(order=order,image=f)
                remember_order(request,order,token)
                request.session.pop('custom_key',None)
                return redirect('receipt',number=order.number)
            except ValidationError as e: form.add_error(None,e)
    return private(render(request,'shop/custom.html',{'form':form}))

class StaffLoginView(LoginView):
    authentication_form=EmailLoginForm
    template_name='shop/login.html'
    def dispatch(self,request,*args,**kwargs):
        if request.method=='POST':
            rate_limit(request,'login-ip',30,900)
            rate_limit(request,'login-account',10,900,identity=digest(request.POST.get('username','').lower()))
        return private(super().dispatch(request,*args,**kwargs))
    def form_valid(self,form):
        u=form.get_user()
        profile=getattr(u,'profile',None)
        if not is_admin(u) and not (profile and profile.active):
            form.add_error(None,'الحساب غير فعال'); return self.form_invalid(form)
        return super().form_valid(form)
    def get_success_url(self): return super().get_success_url() if self.request.GET.get('next') else '/admin/' if is_admin(self.request.user) else '/worker/'

@require_POST
def signout(request):
    logout(request); return redirect('/worker/login/')

@staff_required
def account(request):
    if request.path.startswith('/admin/') and not is_admin(request.user): raise PermissionDenied()
    form=AccountForm(instance=request.user)
    password_form=PasswordChangeForm(request.user)
    if request.method=='POST':
        rate_limit(request,'account',20,600)
        if request.POST.get('action')=='password':
            password_form=PasswordChangeForm(request.user,request.POST)
            if password_form.is_valid():
                u=password_form.save(); update_session_auth_hash(request,u)
                messages.success(request,'تم تغيير كلمة المرور'); return redirect(request.path)
        else:
            form=AccountForm(request.POST,instance=request.user)
            if form.is_valid():
                form.save()
                if hasattr(request.user,'profile'):
                    request.user.profile.display_name=request.user.get_full_name() or request.user.email
                    request.user.profile.save(update_fields=['display_name'])
                messages.success(request,'تم حفظ الحساب'); return redirect(request.path)
    return private(render(request,'shop/account.html',{'form':form,'password_form':password_form,'admin_mode':is_admin(request.user)}))

@staff_required
def work(request):
    admin_mode=request.path.startswith('/admin/')
    if admin_mode and not is_admin(request.user): raise PermissionDenied()
    qs=worker_orders(request.user)
    q=request.GET.get('q','')[:80]
    if q: qs=qs.filter(Q(number__icontains=q)|Q(items__name_ar__icontains=q)).distinct()
    status=request.GET.get('status','')
    if status.isdigit(): qs=qs.filter(status_id=int(status))
    return private(render(request,'shop/work.html',{'orders':Paginator(qs,30).get_page(request.GET.get('page')),'statuses':OrderStatus.objects.filter(active=True),'admin_mode':admin_mode,'q':q}))

@staff_required
def work_detail(request,pk):
    admin_mode=request.path.startswith('/admin/')
    if admin_mode and not is_admin(request.user): raise PermissionDenied()
    order=get_object_or_404(worker_orders(request.user),pk=pk)
    if request.method=='POST':
        action=request.POST.get('action')
        try:
            if action=='status':
                change_status(request.user,pk,request.POST.get('status'),request.POST.get('expected'))
                messages.success(request,'تم تحديث الحالة')
            elif action=='note':
                if not can(request.user,'add_notes'): raise PermissionDenied()
                note=request.POST.get('note','').strip()
                if not note or len(note)>3000: raise ValidationError('اكتب ملاحظة حتى 3000 حرف')
                WorkNote.objects.create(order=order,author=request.user,text=note)
            elif action=='assign':
                if not is_admin(request.user): raise PermissionDenied()
                assignee=request.POST.get('assignee')
                try:
                    user=User.objects.get(pk=assignee,profile__active=True,is_active=True) if assignee else None
                except (User.DoesNotExist,ValueError,TypeError):
                    raise ValidationError('اختر عاملًا فعالًا من القائمة')
                order.assigned_to=user; order.save(update_fields=['assigned_to','updated_at'])
            else: raise ValidationError('عملية غير صالحة')
        except ValidationError as e: messages.error(request,str(e))
        return redirect(request.path)
    statuses=list(OrderStatus.objects.filter(active=True,cancelled=False))
    previous=None; following=None
    for i,s in enumerate(statuses):
        if s.pk==order.status_id:
            previous=statuses[i-1] if i>0 else None
            following=statuses[i+1] if i+1<len(statuses) else None
    return private(render(request,'shop/work_detail.html',{'order':order,'admin_mode':admin_mode,'can_status':can(request.user,'update_status'),'can_previous':can(request.user,'previous_stage'),'can_phone':can(request.user,'view_phone'),'can_address':can(request.user,'view_address'),'can_notes':can(request.user,'add_notes'),'previous':previous,'following':following,'statuses':OrderStatus.objects.filter(active=True),'workers':User.objects.filter(is_active=True,profile__active=True)}))

@staff_required
@require_GET
def custom_image(request,pk):
    image=get_object_or_404(CustomOrderImage,pk=pk)
    get_object_or_404(worker_orders(request.user),pk=image.order_id)
    return private(FileResponse(image.image.open('rb'),content_type='image/jpeg'))

class StorePasswordResetView(PasswordResetView):
    template_name='registration/password_reset_form.html'
    email_template_name='registration/password_reset_email.html'
    subject_template_name='registration/password_reset_subject.txt'
    def dispatch(self,request,*args,**kwargs):
        if not settings.EMAIL_HOST or not settings.DEFAULT_FROM_EMAIL:
            return render(request,'registration/reset_unavailable.html',status=503)
        if request.method=='POST': rate_limit(request,'reset',5,3600)
        return super().dispatch(request,*args,**kwargs)

@require_GET
def catalog_api(request):
    qs=visible_products().prefetch_related('options','images')[:100]
    return JsonResponse({'currency':StoreSettings.get().currency,'products':[{'id':p.pk,'name_ar':p.name_ar,'name_en':p.name_en,'price':str(p.price),'available':p.available,'options':[{'id':o.pk,'kind':o.kind,'name_ar':o.name_ar,'name_en':o.name_en,'additional_price':str(o.additional_price)} for o in p.options.filter(active=True)]} for p in qs]})

@require_POST
def track_api(request):
    rate_limit(request,'tracking',20,600)
    try:
        data=json.loads(request.body)
        number=str(data['number'])[:50]; token=str(data['token'])[:128]
    except (ValueError,KeyError,TypeError): return JsonResponse({'error':'Invalid request'},status=400)
    order=verify_tracking(number,token)
    if not order: return private(JsonResponse({'error':'Not found'},status=404))
    return private(JsonResponse({'number':order.number,'status':order.status.name_ar,'currency':order.currency,'total':str(order.total),'items':[{'name':i.name_ar,'quantity':i.quantity,'unit_price':str(i.unit_price)} for i in order.items.all()]}))

@require_GET
def health(request):
    from django.db import connection
    with connection.cursor() as cursor: cursor.execute('SELECT 1'); cursor.fetchone()
    return JsonResponse({'status':'ok'})


def setup_admin(request):
    # Setup is disabled without a securely configured token, and permanently closes
    # once any administrator exists (including an inactive administrator).
    from django.http import Http404
    if len(settings.STORE_SETUP_TOKEN) < 32 or User.objects.filter(is_superuser=True).exists():
        raise Http404()
    form=AdminSetupForm(request.POST or None)
    if request.method=='POST':
        rate_limit(request,'store-setup',5,900)
        if form.is_valid():
            if not hmac.compare_digest(form.cleaned_data['setup_code'].encode(),settings.STORE_SETUP_TOKEN.encode()):
                form.add_error('setup_code','رمز الإعداد غير صحيح')
            else:
                with transaction.atomic():
                    StoreSettings.objects.select_for_update().get(pk=1)
                    if User.objects.filter(is_superuser=True).exists(): raise Http404()
                    user=form.save(commit=False)
                    user.is_superuser=True;user.is_staff=True;user.is_active=True
                    user.save()
                login(request,user,backend='django.contrib.auth.backends.ModelBackend')
                messages.success(request,'تم إنشاء حساب المدير. أضف بيانات محلك الآن.')
                return redirect('/admin/')
    return private(render(request,'shop/setup.html',{'form':form}))

@require_GET
def public_upload(request,filename):
    # Only UUID-named raster images generated by our upload path may be served.
    # Never serve private/custom, arbitrary paths, or user-supplied active content.
    import re
    import mimetypes
    from django.http import Http404
    from django.core.files.storage import default_storage
    if not settings.SERVE_PUBLIC_UPLOADS or not re.fullmatch(r'[0-9a-f]{32}\.(?:jpg|jpeg|png|webp)',filename):
        raise Http404()
    try: file=default_storage.open('images/'+filename,'rb')
    except FileNotFoundError: raise Http404()
    response=FileResponse(file,content_type=mimetypes.guess_type(filename)[0] or 'application/octet-stream')
    response['X-Content-Type-Options']='nosniff'
    response['Cache-Control']='public, max-age=3600'
    return response
