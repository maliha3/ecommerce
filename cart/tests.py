from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from store.models import Category, Product, ProductVariant


class CartTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        category = Category.objects.create(name="Shoes")
        cls.product = Product.objects.create(
            category=category, name="Court Shoe", price=Decimal("900")
        )
        cls.medium = ProductVariant.objects.create(
            product=cls.product, size="38", stock=4
        )
        cls.sold_out = ProductVariant.objects.create(
            product=cls.product, size="36", stock=0
        )

    def add(self, variant, quantity=1, **extra):
        return self.client.post(
            reverse("cart:add", args=[self.product.slug]),
            {"variant": variant.id, "quantity": quantity, **extra},
        )

    def test_add_puts_item_in_session(self):
        self.add(self.medium, 2)
        self.assertEqual(
            self.client.session["cart"][str(self.medium.id)]["quantity"], 2
        )

    def test_add_accumulates_then_caps_at_stock(self):
        self.add(self.medium, 3)
        self.add(self.medium, 3)
        self.assertEqual(
            self.client.session["cart"][str(self.medium.id)]["quantity"], 4
        )

    def test_override_sets_quantity_instead_of_adding(self):
        self.add(self.medium, 3)
        self.add(self.medium, 1, override="on")
        self.assertEqual(
            self.client.session["cart"][str(self.medium.id)]["quantity"], 1
        )

    def test_sold_out_size_is_rejected(self):
        response = self.add(self.sold_out, 1)
        self.assertEqual(response.status_code, 302)
        self.assertNotIn(str(self.sold_out.id), self.client.session.get("cart", {}))

    def test_ajax_add_returns_json_count(self):
        response = self.client.post(
            reverse("cart:add", args=[self.product.slug]),
            {"variant": self.medium.id, "quantity": 2},
            headers={"x-requested-with": "XMLHttpRequest"},
        )
        self.assertJSONNotEqual(response.content.decode(), {})
        self.assertTrue(response.json()["ok"])
        self.assertEqual(response.json()["count"], 2)

    def test_session_stays_json_serializable(self):
        """Reading the cart must not write model objects back to the session."""
        self.add(self.medium, 1)
        self.client.get(reverse("cart:detail"))
        for row in self.client.session["cart"].values():
            self.assertEqual(set(row), {"quantity", "price"})

    def test_remove_empties_the_bag(self):
        self.add(self.medium, 1)
        self.client.post(reverse("cart:remove", args=[self.medium.id]))
        self.assertEqual(self.client.session.get("cart"), {})

    def test_add_requires_post(self):
        response = self.client.get(reverse("cart:add", args=[self.product.slug]))
        self.assertEqual(response.status_code, 405)

    def test_prune_trims_rows_that_outgrew_stock(self):
        self.add(self.medium, 4)
        self.medium.stock = 1
        self.medium.save()
        self.client.get(reverse("cart:detail"))
        self.assertEqual(
            self.client.session["cart"][str(self.medium.id)]["quantity"], 1
        )
