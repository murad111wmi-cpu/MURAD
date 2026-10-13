import re
from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm, UserChangeForm
from django.contrib.auth.password_validation import validate_password
from .models import *
from .validators import image_upload

class EmailLoginForm(AuthenticationForm):
    username=forms.EmailField(label='البريد الإلكتروني',widget=forms.EmailInput(attrs={'autocomplete':'username'}))

class StaffCreationForm(UserCreationForm):
    class Meta: model=User; fields=('email','first_name','last_name')
    def clean_email(self): return self.cleaned_data['email'].lower()

class CheckoutForm(forms.Form):
    name=forms.CharField(label='الاسم / Name',max_length=160)
    phone=forms.CharField(label='رقم الهاتف / Phone',max_length=40)
    fulfillment=forms.ModelChoiceField(label='طريقة الاستلام / Fulfillment',queryset=FulfillmentMethod.objects.none())
    zone=forms.ModelChoiceField(label='منطقة التوصيل / Delivery area',queryset=DeliveryZone.objects.none(),required=False)
    branch=forms.ModelChoiceField(label='فرع الاستلام / Pickup branch',queryset=Branch.objects.none(),required=False)
    address=forms.CharField(label='العنوان / Address',widget=forms.Textarea(attrs={'rows':2}),required=False,max_length=1000)
    notes=forms.CharField(label='الملاحظات / Notes',widget=forms.Textarea(attrs={'rows':2}),required=False,max_length=3000)
    website=forms.CharField(required=False,widget=forms.HiddenInput)
    quote=forms.CharField(widget=forms.HiddenInput)
    request_key=forms.UUIDField(widget=forms.HiddenInput)
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        s=StoreSettings.get()
        self.fields['fulfillment'].queryset=FulfillmentMethod.objects.filter(active=True)
        self.fields['zone'].queryset=DeliveryZone.objects.filter(active=True)
        self.fields['branch'].queryset=Branch.objects.filter(active=True)
        for name in ['address','notes']:
            mode=getattr(s,f'{name}_mode')
            self.fields[name].required=mode=='required'
            if mode=='hidden': self.fields[name].widget=forms.HiddenInput()
    def clean_phone(self):
        phone=re.sub(r'[\s()-]','',self.cleaned_data['phone'])
        if not re.fullmatch(r'\+?[0-9]{7,15}',phone): raise forms.ValidationError('أدخل رقم هاتف صحيحًا مع رمز الدولة')
        return phone
    def clean_website(self):
        if self.cleaned_data.get('website'): raise forms.ValidationError('الطلب غير صالح')
        return ''
    def clean(self):
        c=super().clean()
        m=c.get('fulfillment')
        if m and m.kind=='delivery':
            if not c.get('zone'): self.add_error('zone','اختر منطقة التوصيل')
            if not c.get('address'): self.add_error('address','أدخل عنوان التوصيل')
        if m and m.kind=='pickup' and not c.get('branch'): self.add_error('branch','اختر فرع الاستلام')
        return c

class MultipleInput(forms.ClearableFileInput): allow_multiple_selected=True
class MultipleImages(forms.FileField):
    def __init__(self,*args,**kwargs):
        kwargs['widget']=MultipleInput(attrs={'accept':'image/jpeg,image/png,image/webp'})
        super().__init__(*args,**kwargs)
    def clean(self,data,initial=None):
        files=data if isinstance(data,(list,tuple)) else [data] if data else []
        if len(files)>5: raise forms.ValidationError('ارفع 5 صور كحد أقصى')
        result=[]
        for f in files:
            f=super().clean(f,initial); image_upload(f); result.append(f)
        return result

class CustomOrderForm(CheckoutForm):
    piece=forms.CharField(label='نوع القطعة / Piece',max_length=160)
    description=forms.CharField(label='الوصف / Description',widget=forms.Textarea,max_length=5000)
    dimensions=forms.CharField(label='المقاسات / Dimensions',required=False,max_length=500)
    color=forms.CharField(label='اللون / Color',required=False,max_length=120)
    wood=forms.CharField(label='نوع الخشب / Wood',required=False,max_length=120)
    images=MultipleImages(label='صور مرجعية / Reference images',required=False)
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        for field in ['fulfillment','zone','branch','quote','address']: self.fields.pop(field,None)
    def clean(self): return forms.Form.clean(self)

class AccountForm(forms.ModelForm):
    current_password=forms.CharField(label='كلمة المرور الحالية',widget=forms.PasswordInput)
    class Meta: model=User; fields=('email','first_name','last_name')
    def clean_email(self): return self.cleaned_data['email'].lower()
    def clean_current_password(self):
        value=self.cleaned_data['current_password']
        if not self.instance.check_password(value): raise forms.ValidationError('كلمة المرور غير صحيحة')
        return value

class StaffChangeForm(UserChangeForm):
    class Meta: model=User; fields="__all__"
    def clean_email(self): return self.cleaned_data["email"].lower()

class AdminSetupForm(StaffCreationForm):
    setup_code = forms.CharField(label='رمز إعداد المتجر من الاستضافة / Setup token', max_length=256, strip=False,
                                widget=forms.PasswordInput(attrs={'autocomplete':'off'}))
