from django import template
from decimal import Decimal
register=template.Library()
@register.simple_tag(takes_context=True)
def tr(context,ar,en): return en if context.get('lang')=='en' else ar
@register.simple_tag(takes_context=True)
def label(context,obj): return obj.label(context.get('lang','ar'))
@register.simple_tag(takes_context=True)
def text(context,obj,field):
    lang=context.get('lang','ar')
    return getattr(obj,f'{field}_{lang}','') or getattr(obj,f'{field}_ar','')
@register.filter
def money(value,currency='JOD'):
    from shop.currencies import currency_digits
    digits=currency_digits(currency)
    return f'{Decimal(value):,.{digits}f} {currency}'
@register.filter
def getkey(obj,key): return obj.get(key,'')
