from django.conf import settings

from .models import Category


def storefront(request):
    """Shop-wide values every template needs: nav sections and branding."""
    return {
        "nav_categories": Category.objects.filter(is_active=True),
        "shop_name": settings.SHOP_NAME,
        "shop_tagline": settings.SHOP_TAGLINE,
        "shop_phone": settings.SHOP_PHONE,
        "currency": settings.CURRENCY_SYMBOL,
    }
