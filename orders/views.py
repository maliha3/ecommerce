from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404, redirect, render

from cart.cart import Cart
from store.models import ProductVariant

from .forms import CheckoutForm
from .models import Order, OrderItem


def checkout(request):
    cart = Cart(request)

    for note in cart.prune():
        messages.warning(request, note)

    if len(cart) == 0:
        messages.info(request, "Your cart is empty.")
        return redirect("store:catalog")

    if request.method == "POST":
        form = CheckoutForm(request.POST)
        if form.is_valid():
            order = _place_order(request, cart, form)
            if order is not None:
                cart.clear()
                # Lets the thank-you page be shown to this browser only.
                request.session["order_number"] = order.order_number
                return redirect("orders:success", order_number=order.order_number)
    else:
        form = CheckoutForm()

    return render(
        request,
        "orders/checkout.html",
        {
            "form": form,
            "bkash_number": settings.BKASH_NUMBER,
            "nagad_number": settings.NAGAD_NUMBER,
            "charge_dhaka": settings.DELIVERY_CHARGE_DHAKA,
            "charge_outside": settings.DELIVERY_CHARGE_OUTSIDE,
        },
    )


def _place_order(request, cart, form):
    """Write the order and draw down stock atomically.

    Returns None (with a message set) if stock ran out between the cart page
    and the submit — the customer is sent back to fix their cart.
    """
    rows = list(cart)

    with transaction.atomic():
        # Lock the variant rows so two shoppers cannot buy the same last unit.
        locked = {
            v.id: v
            for v in ProductVariant.objects.select_for_update().filter(
                id__in=[row["variant"].id for row in rows]
            )
        }

        for row in rows:
            variant = locked.get(row["variant"].id)
            if variant is None or variant.stock < row["quantity"]:
                available = 0 if variant is None else variant.stock
                messages.error(
                    request,
                    f"Only {available} left of {row['product'].name} "
                    f"({row['variant'].get_size_display()}). Please update your cart.",
                )
                transaction.set_rollback(True)
                return None

        order = form.save(commit=False)
        order.delivery_charge = order.charge_for_area()
        order.save()

        OrderItem.objects.bulk_create(
            [
                OrderItem(
                    order=order,
                    variant=row["variant"],
                    product_name=row["product"].name,
                    size=row["variant"].get_size_display(),
                    price=row["price"],
                    quantity=row["quantity"],
                )
                for row in rows
            ]
        )

        for row in rows:
            ProductVariant.objects.filter(id=row["variant"].id).update(
                stock=F("stock") - row["quantity"]
            )

    return order


def success(request, order_number):
    """Thank-you page, visible only to the session that placed the order."""
    if request.session.get("order_number") != order_number:
        messages.error(request, "That order confirmation is no longer available.")
        return redirect("store:catalog")

    order = get_object_or_404(
        Order.objects.prefetch_related("items"), order_number=order_number
    )
    return render(
        request,
        "orders/success.html",
        {"order": order, "shop_phone": settings.SHOP_PHONE},
    )
