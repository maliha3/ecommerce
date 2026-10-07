from decimal import Decimal

from django.conf import settings

from store.models import ProductVariant


class Cart:
    """A session-backed cart keyed by product variant (product + size).

    Session shape: ``{variant_id: {"quantity": int, "price": "399.00"}}``.
    The price is snapshotted on add so the total cannot shift under the
    customer mid-session if the client edits a price in the admin.
    """

    def __init__(self, request):
        self.session = request.session
        cart = self.session.get(settings.CART_SESSION_ID)
        if cart is None:
            cart = self.session[settings.CART_SESSION_ID] = {}
        self.cart = cart

    # -- mutation ---------------------------------------------------------

    def add(self, variant, quantity=1, override_quantity=False):
        """Add or set the quantity for a variant, capped at available stock."""
        key = str(variant.id)
        if key not in self.cart:
            self.cart[key] = {"quantity": 0, "price": str(variant.price)}

        if override_quantity:
            new_quantity = quantity
        else:
            new_quantity = self.cart[key]["quantity"] + quantity

        new_quantity = min(new_quantity, variant.stock)
        if new_quantity <= 0:
            self.remove(variant)
            return 0

        self.cart[key]["quantity"] = new_quantity
        # Refresh the snapshot so a sale that started since adding is honoured.
        self.cart[key]["price"] = str(variant.price)
        self.save()
        return new_quantity

    def remove(self, variant):
        self.cart.pop(str(variant.id), None)
        self.save()

    def clear(self):
        self.session.pop(settings.CART_SESSION_ID, None)
        self.session.modified = True

    def save(self):
        self.session.modified = True

    # -- reading ----------------------------------------------------------

    def __iter__(self):
        """Yield rows with the live ProductVariant attached.

        Builds fresh dicts rather than annotating the session rows: anything
        written back into the session has to stay JSON-serializable.
        """
        variants = {
            str(v.id): v
            for v in ProductVariant.objects.filter(
                id__in=self.cart.keys()
            ).select_related("product", "product__category")
        }

        for key, row in self.cart.items():
            variant = variants.get(key)
            if variant is None:
                continue  # variant was deleted; skip the orphan row
            price = Decimal(row["price"])
            quantity = row["quantity"]
            yield {
                "variant": variant,
                "product": variant.product,
                "quantity": quantity,
                "price": price,
                "total_price": price * quantity,
                "over_stock": quantity > variant.stock,
            }

    def __len__(self):
        return sum(row["quantity"] for row in self.cart.values())

    @property
    def subtotal(self) -> Decimal:
        total = sum(
            Decimal(row["price"]) * row["quantity"] for row in self.cart.values()
        )
        return Decimal(total or 0)

    def delivery_charge(self, inside_dhaka=True) -> Decimal:
        if not len(self):
            return Decimal("0")
        fee = (
            settings.DELIVERY_CHARGE_DHAKA
            if inside_dhaka
            else settings.DELIVERY_CHARGE_OUTSIDE
        )
        return Decimal(fee)

    def total(self, inside_dhaka=True) -> Decimal:
        return self.subtotal + self.delivery_charge(inside_dhaka)

    def prune(self):
        """Drop rows whose stock is gone; trim rows that exceed stock.

        Returns the list of human-readable adjustments made.
        """
        notes = []
        variants = {
            str(v.id): v
            for v in ProductVariant.objects.filter(
                id__in=self.cart.keys()
            ).select_related("product")
        }
        for key in list(self.cart.keys()):
            variant = variants.get(key)
            if variant is None or variant.stock == 0:
                self.cart.pop(key)
                notes.append("An item in your cart is no longer available.")
                continue
            if self.cart[key]["quantity"] > variant.stock:
                self.cart[key]["quantity"] = variant.stock
                notes.append(
                    f"Only {variant.stock} left of {variant.product.name} "
                    f"({variant.get_size_display()}); your cart was adjusted."
                )
        if notes:
            self.save()
        return notes
