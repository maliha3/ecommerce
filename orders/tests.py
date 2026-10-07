from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from store.models import Category, Product, ProductVariant

from .models import Order


class CheckoutTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name="Shoes")
        self.product = Product.objects.create(
            category=category, name="Court Shoe", price=Decimal("700")
        )
        self.variant = ProductVariant.objects.create(
            product=self.product, size="38", stock=5
        )
        self.client.post(
            reverse("cart:add", args=[self.product.slug]),
            {"variant": self.variant.id, "quantity": 2},
        )

    DETAILS = {
        "full_name": "Rafi Ahmed",
        "phone": "01712345678",
        "address": "12 Road 5, Dhanmondi",
        "city": "Dhaka",
        "area": "dhaka",
    }

    def post_checkout(self, **extra):
        return self.client.post(reverse("orders:checkout"), {**self.DETAILS, **extra})

    # -- cash on delivery -------------------------------------------------

    def test_cod_order_is_placed(self):
        response = self.post_checkout(payment_method="cod")
        self.assertEqual(response.status_code, 302)
        order = Order.objects.get()
        self.assertEqual(order.payment_status, Order.PaymentStatus.UNPAID)
        self.assertEqual(order.delivery_charge, Decimal("60"))
        self.assertEqual(order.total, Decimal("1400") + Decimal("60"))

    def test_cod_discards_a_stray_transaction_id(self):
        self.post_checkout(payment_method="cod", transaction_id="LEFTOVER123")
        self.assertEqual(Order.objects.get().transaction_id, "")

    def test_outside_dhaka_costs_more_to_deliver(self):
        self.post_checkout(payment_method="cod", area="outside", city="Sylhet")
        self.assertEqual(Order.objects.get().delivery_charge, Decimal("120"))

    # -- manual wallet transfer ------------------------------------------

    def test_bkash_requires_a_transaction_id(self):
        response = self.post_checkout(payment_method="bkash")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Order.objects.exists())
        self.assertFormError(
            response.context["form"],
            "transaction_id",
            "Please send the payment first, then enter the TrxID from the "
            "confirmation SMS.",
        )

    def test_bkash_requires_a_sender_number(self):
        self.post_checkout(payment_method="bkash", transaction_id="9F2K7XQ1AB")
        self.assertFalse(Order.objects.exists())

    def test_bkash_rejects_an_implausibly_short_trxid(self):
        self.post_checkout(
            payment_method="bkash", transaction_id="abc", sender_number="01712345678"
        )
        self.assertFalse(Order.objects.exists())

    def test_bkash_order_awaits_verification(self):
        self.post_checkout(
            payment_method="bkash",
            transaction_id="9F2K7XQ1AB",
            sender_number="01787654321",
        )
        order = Order.objects.get()
        self.assertEqual(order.payment_status, Order.PaymentStatus.AWAITING)
        self.assertEqual(order.transaction_id, "9F2K7XQ1AB")
        self.assertTrue(order.is_manual_transfer)

    # -- stock and order contents ----------------------------------------

    def test_stock_is_drawn_down(self):
        self.post_checkout(payment_method="cod")
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 3)

    def test_order_snapshots_name_size_and_price(self):
        self.post_checkout(payment_method="cod")
        item = Order.objects.get().items.get()
        self.assertEqual(item.product_name, "Court Shoe")
        self.assertEqual(item.size, "EU 38")
        self.assertEqual(item.price, Decimal("700"))
        self.product.name = "Renamed Shoe"
        self.product.save()
        item.refresh_from_db()
        self.assertEqual(item.product_name, "Court Shoe")

    def test_order_is_refused_when_stock_vanished(self):
        self.variant.stock = 1
        self.variant.save(update_fields=["stock"])
        # prune() trims the cart to the 1 remaining unit rather than overselling.
        self.post_checkout(payment_method="cod")
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 0)
        self.assertEqual(Order.objects.get().items.get().quantity, 1)

    def test_cart_is_cleared_after_ordering(self):
        self.post_checkout(payment_method="cod")
        self.assertFalse(self.client.session.get("cart"))

    def test_order_numbers_are_unique(self):
        self.post_checkout(payment_method="cod")
        self.client.post(
            reverse("cart:add", args=[self.product.slug]),
            {"variant": self.variant.id, "quantity": 1},
        )
        self.post_checkout(payment_method="cod")
        numbers = set(Order.objects.values_list("order_number", flat=True))
        self.assertEqual(len(numbers), 2)
        self.assertTrue(all(n.startswith("TC-") for n in numbers))

    def test_empty_bag_cannot_reach_checkout(self):
        self.client.post(reverse("cart:remove", args=[self.variant.id]))
        response = self.client.get(reverse("orders:checkout"))
        self.assertRedirects(response, reverse("store:catalog"))


class ConfirmationPageTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name="Shoes")
        product = Product.objects.create(
            category=category, name="Court Shoe", price=Decimal("700")
        )
        variant = ProductVariant.objects.create(product=product, size="38", stock=5)
        self.client.post(
            reverse("cart:add", args=[product.slug]),
            {"variant": variant.id, "quantity": 1},
        )
        self.client.post(
            reverse("orders:checkout"),
            {**CheckoutTests.DETAILS, "payment_method": "cod"},
        )
        self.order = Order.objects.get()

    def test_buyer_sees_their_confirmation(self):
        response = self.client.get(
            reverse("orders:success", args=[self.order.order_number])
        )
        self.assertContains(response, self.order.order_number)

    def test_another_visitor_cannot_read_the_order(self):
        other = self.client_class()
        response = other.get(reverse("orders:success", args=[self.order.order_number]))
        self.assertRedirects(response, reverse("store:catalog"))
