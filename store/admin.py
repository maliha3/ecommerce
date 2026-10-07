from django.contrib import admin
from django.db.models import Sum
from django.utils.html import format_html

from .models import Brand, Category, Product, ProductVariant


class ProductVariantInline(admin.TabularInline):
    """Size rows edited right on the product page."""

    model = ProductVariant
    extra = 4
    fields = ["size", "stock", "sku"]
    verbose_name = "size"
    verbose_name_plural = "Sizes and stock"


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "product_count", "is_active", "sort_order"]
    list_editable = ["is_active", "sort_order"]
    list_filter = ["is_active"]
    search_fields = ["name", "description"]
    prepopulated_fields = {"slug": ("name",)}
    fields = ["name", "slug", "description", "is_active", "sort_order"]

    @admin.display(description="products")
    def product_count(self, obj):
        return obj.products.count()


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ["name", "kind", "country", "product_count", "is_active", "sort_order"]
    list_editable = ["kind", "is_active", "sort_order"]
    list_filter = ["kind", "is_active"]
    search_fields = ["name", "country"]
    prepopulated_fields = {"slug": ("name",)}

    @admin.display(description="products")
    def product_count(self, obj):
        return obj.products.count()


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        "thumbnail",
        "name",
        "brand",
        "category",
        "price",
        "sale_price",
        "stock_total",
        "is_active",
        "is_featured",
    ]
    list_display_links = ["thumbnail", "name"]
    # The client can retouch prices and stock flags straight from the list.
    list_editable = ["price", "sale_price", "is_active", "is_featured"]
    list_filter = ["is_active", "is_featured", "category", "brand", "karat", "created"]
    search_fields = ["name", "description", "brand__name"]
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ProductVariantInline]
    readonly_fields = ["preview", "created", "updated"]
    save_on_top = True
    list_per_page = 25

    fieldsets = (
        ("Product", {"fields": ("name", "slug", "brand", "category", "description")}),
        (
            "Pricing",
            {
                "fields": ("price", "sale_price"),
                "description": "Leave the sale price blank unless the item is discounted.",
            },
        ),
        ("Photo", {"fields": ("image", "preview")}),
        (
            "Gold",
            {
                "fields": ("karat", "weight_grams"),
                "classes": ("collapse",),
                "description": "Fill these in for gold items only.",
            },
        ),
        ("Visibility", {"fields": ("is_active", "is_featured")}),
        ("Record", {"fields": ("created", "updated"), "classes": ("collapse",)}),
    )

    actions = ["mark_active", "mark_inactive", "clear_sale_price"]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("category", "brand")
            .annotate(_stock=Sum("variants__stock"))
        )

    @admin.display(description="")
    def thumbnail(self, obj):
        if not obj.image:
            return format_html(
                '<div style="width:44px;height:44px;border-radius:6px;background:#e9e9e6;'
                'display:flex;align-items:center;justify-content:center;color:#888;'
                'font-size:11px">none</div>'
            )
        return format_html(
            '<img src="{}" style="width:44px;height:44px;object-fit:cover;'
            'border-radius:6px" />',
            obj.image.url,
        )

    @admin.display(description="Current photo")
    def preview(self, obj):
        if not obj.image:
            return "No image uploaded yet."
        return format_html(
            '<img src="{}" style="max-width:280px;border-radius:8px" />', obj.image.url
        )

    @admin.display(description="stock", ordering="_stock")
    def stock_total(self, obj):
        total = obj._stock or 0
        if total == 0:
            color, label = "#b3261e", "out of stock"
        elif total <= 5:
            color, label = "#a35b00", f"{total} left"
        else:
            color, label = "#1f6f4a", f"{total} in stock"
        return format_html('<b style="color:{}">{}</b>', color, label)

    @admin.action(description="Publish selected products")
    def mark_active(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} product(s) published.")

    @admin.action(description="Hide selected products")
    def mark_inactive(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} product(s) hidden.")

    @admin.action(description="End sale (clear sale price)")
    def clear_sale_price(self, request, queryset):
        updated = queryset.update(sale_price=None)
        self.message_user(request, f"Sale ended on {updated} product(s).")


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    """Standalone view for a quick stock-take across every size."""

    list_display = ["product", "size", "stock", "sku"]
    list_editable = ["stock", "sku"]
    list_filter = ["size", "product__category"]
    search_fields = ["product__name", "sku"]
    list_select_related = ["product"]
