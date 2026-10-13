from django.urls import path,include
from django.views.generic import RedirectView
from django.conf import settings
from django.contrib.auth import views as auth
from shop.admin import site
from shop import views
urlpatterns=[
    path('',views.home,name='home'),path('setup/',views.setup_admin,name='setup_admin'),path('favicon.ico',RedirectView.as_view(url='/static/shop/workshop.svg')),path('admin/password_reset/',views.StorePasswordResetView.as_view(),name='admin_password_reset'),path('products/',views.products,name='products'),path('product/<int:pk>/',views.product,name='product'),path('product/<int:pk>/add/',views.add_cart,name='add_cart'),path('cart/',views.cart,name='cart'),path('cart/clear/',views.clear_cart),path('order/',views.checkout,name='checkout'),path('order/receipt/<str:number>/',views.receipt,name='receipt'),path('track-order/',views.track,name='track'),path('custom-order/',views.custom_order,name='custom'),path('language/',views.language),
    path('admin/worker-center/',views.work,name='worker_center'),path('admin/worker-center/<uuid:pk>/',views.work_detail,name='admin_work_detail'),path('admin/account/',views.account,name='admin_account'),path('admin/',site.urls),
    path('worker/login/',views.StaffLoginView.as_view(),name='worker_login'),path('worker/',views.work,name='worker'),path('worker/orders/',views.work),path('worker/orders/<uuid:pk>/',views.work_detail,name='work_detail'),path('worker/account/',views.account,name='account'),path('logout/',views.signout,name='logout'),path('private-image/<int:pk>/',views.custom_image,name='custom_image'),
    path('password-reset/',views.StorePasswordResetView.as_view(),name='password_reset'),path('password-reset/done/',auth.PasswordResetDoneView.as_view(),name='password_reset_done'),path('reset/<uidb64>/<token>/',auth.PasswordResetConfirmView.as_view(),name='password_reset_confirm'),path('reset/done/',auth.PasswordResetCompleteView.as_view(),name='password_reset_complete'),
    path('api/catalog/',views.catalog_api),path('api/track/',views.track_api),path('health/',views.health),
]
if settings.SERVE_PUBLIC_UPLOADS:
    urlpatterns += [path('media/images/<str:filename>',views.public_upload)]
if settings.DEBUG:
    from django.views.static import serve
    from django.http import Http404
    def public_media(request,path):
        if not path.startswith('images/'): raise Http404()
        return serve(request,path,document_root=settings.MEDIA_ROOT)
    urlpatterns+=[path('media/<path:path>',public_media)]
