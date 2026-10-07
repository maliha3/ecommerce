from django.contrib import admin
from django.utils.html import format_html

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ["product_name", "size", "price", "quantity", "line_total"]
    fields = ["product_name", "size", "price", "quantity", "line_total"]
    can_delete = False

    def has_add_permission(self, request, obj):
        return False

    @admin.display(description="line total")
    def line_total(self, obj):
        return f"{obj.cost:.2f}"


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """The order desk: what came in, how it was paid, where it is going."""

    list_display = [
        "order_number",
        "created_short",
        "full_name",
        "phone",
        "payment_badge",
        "trx",
        "total_display",
        "status",
    ]
    list_display_links = ["order_number"]
    list_editable = ["status"]
    list_filter = ["status", "payment_method", "payment_status", "area", "created"]
    search_fields = [
        "order_number",
        "full_name",
        "phone",
        "email",
        "transaction_id",
        "sender_number",
    ]
    date_hierarchy = "created"
    inlines = [OrderItemInline]
    save_on_top = True
    list_per_page = 30

    readonly_fields = [
        "order_number",
        "created",
        "updated",
        "subtotal_display",
        "total_display",
    ]

    fieldsets = (
        (
            "Order",
            {
                "fields": (
                    "order_number",
                    "status",
                    ("created", "updated"),
                )
            },
        ),
        (
            "Payment",
            {
                "fields": (
                    "payment_method",
                    "payment_status",
                    "transaction_id",
                    "sender_number",
                ),
                "description": (
                    "For bKash/Nagad orders: check the TrxID against your wallet "
                    "statement, then set the payment status to Verified."
                ),
            },
        ),
        (
            "Customer and delivery",
            {
                "fields": (
                    "full_name",
                    "phone",
                    "email",
                    "address",
                    "city",
                    "area",
                    "note",
                )
            },
        ),
        (
            "Totals",
            {"fields": ("subtotal_display", "delivery_charge", "total_display")},
        ),
    )

    actions = [
        "mark_payment_verified",
        "mark_confirmed",
        "mark_shipped",
        "mark_delivered",
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("items")

    # -- display helpers -------------------------------------------------

    @admin.display(description="placed", ordering="created")
    def created_short(self, obj):
        return obj.created.strftime("%d %b, %H:%M")

    @admin.display(description="payment")
    def payment_badge(self, obj):
        colors = {
            obj.PaymentStatus.VERIFIED: "#1f6f4a",
            obj.PaymentStatus.AWAITING: "#a35b00",
            obj.PaymentStatus.REJECTED: "#b3261e",
            obj.PaymentStatus.UNPAID: "#555",
        }
        return format_html(
            '{}<br><b style="color:{}">{}</b>',
            obj.get_payment_method_display(),
            colors.get(obj.payment_status, "#555"),
            obj.get_payment_status_display(),
        )

    @admin.display(description="TrxID")
    def trx(self, obj):
        if not obj.transaction_id:
            return format_html('<span style="color:#999">—</span>')
        return format_html(
            '<code style="font-size:12px">{}</code><br>'
            '<span style="color:#666;font-size:11px">from {}</span>',
            obj.transaction_id,
            obj.sender_number or "unknown",
        )

    @admin.display(description="subtotal")
    def subtotal_display(self, obj):
        return f"{obj.subtotal:.2f}"

    @admin.display(description="total")
    def total_display(self, obj):
        return format_html("<b>{}</b>", f"{obj.total:.2f}")

    # -- bulk actions ----------------------------------------------------

    @admin.action(description="Mark payment as verified")
    def mark_payment_verified(self, request, queryset):
        n = queryset.update(payment_status=Order.PaymentStatus.VERIFIED)
        self.message_user(request, f"{n} order(s) marked paid.")

    @admin.action(description="Mark as confirmed")
    def mark_confirmed(self, request, queryset):
        n = queryset.update(status=Order.Status.CONFIRMED)
        self.message_user(request, f"{n} order(s) confirmed.")

    @admin.action(description="Mark as shipped")
    def mark_shipped(self, request, queryset):
        n = queryset.update(status=Order.Status.SHIPPED)
        self.message_user(request, f"{n} order(s) marked shipped.")

    @admin.action(description="Mark as delivered")
    def mark_delivered(self, request, queryset):
        n = queryset.update(status=Order.Status.DELIVERED)
        self.message_user(request, f"{n} order(s) marked delivered.")
