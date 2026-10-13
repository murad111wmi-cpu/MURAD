from .models import StoreSettings, NavigationItem, SocialLink

def store_context(request):
    s=StoreSettings.get()
    lang=s.default_language
    chosen=request.session.get('display_language')
    if s.language_switch and chosen in ['ar','en'] and getattr(s,f'enable_{chosen}',False): lang=chosen
    return {'store':s,'lang':lang,'rtl':lang=='ar','navigation':NavigationItem.objects.filter(active=True),'social_links':SocialLink.objects.filter(active=True),'cart_count':sum(int(l.get('quantity',0)) for l in request.session.get('cart',[]))}
