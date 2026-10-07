from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

admin.site.site_header = f"{settings.SHOP_NAME} administration"
admin.site.site_title = settings.SHOP_NAME
admin.site.index_title = "Shop management"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("cart/", include("cart.urls")),
    # The cart used to live at /bag/; keep old links and bookmarks working.
    path("bag/", RedirectView.as_view(url="/cart/", permanent=True)),
    path("orders/", include("orders.urls")),
    path("", include("store.urls")),
]

# Cloudinary serves media in production; this is the local-development path.
if settings.DEBUG and not settings.USE_CLOUDINARY:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler404 = "store.views.page_not_found"
