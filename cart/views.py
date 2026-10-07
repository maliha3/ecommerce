from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from store.models import Product, ProductVariant

from .cart import Cart
from .forms import AddToCartForm


def _wants_json(request):
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


@require_POST
def cart_add(request, product_slug):
    """Add a chosen size to the cart. Answers JSON for the fetch() path."""
    product = get_object_or_404(Product, slug=product_slug, is_active=True)
    form = AddToCartForm(request.POST, product=product)

    if not form.is_valid():
        error = next(iter(form.errors.values()))[0]
        if _wants_json(request):
            return JsonResponse({"ok": False, "error": error}, status=400)
        messages.error(request, error)
        return redirect(product.get_absolute_url())

    cart = Cart(request)
    variant = form.cleaned_data["variant"]
    placed = cart.add(
        variant=variant,
        quantity=form.cleaned_data["quantity"],
        override_quantity=form.cleaned_data["override"],
    )

    label = f"{product.name} ({variant.get_size_display()})"
    if _wants_json(request):
        return JsonResponse(
            {
                "ok": True,
                "message": f"{label} added to your cart.",
                "count": len(cart),
                "quantity": placed,
            }
        )

    messages.success(request, f"{label} added to your cart.")
    return redirect("cart:detail")


@require_POST
def cart_remove(request, variant_id):
    cart = Cart(request)
    variant = get_object_or_404(ProductVariant, id=variant_id)
    cart.remove(variant)
    messages.info(request, f"Removed {variant.product.name} from your cart.")
    return redirect("cart:detail")


def cart_detail(request):
    cart = Cart(request)
    for note in cart.prune():
        messages.warning(request, note)

    rows = [
        {
            "item": item,
            "form": AddToCartForm(
                initial={
                    "variant": item["variant"].id,
                    "quantity": item["quantity"],
                    "override": True,
                },
                product=item["product"],
            ),
        }
        for item in cart
    ]
    return render(request, "cart/detail.html", {"rows": rows})
