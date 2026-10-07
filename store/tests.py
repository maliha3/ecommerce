from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from .models import Brand, Category, Product, ProductVariant


class ProductPricingTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Shoes")
        self.product = Product.objects.create(
            category=self.category, name="Plain Pump", price=Decimal("1000")
        )

    def test_slug_autofills(self):
        self.assertEqual(self.product.slug, "plain-pump")

    def test_current_price_without_sale(self):
        self.assertEqual(self.product.current_price, Decimal("1000"))
        self.assertFalse(self.product.on_sale)
        self.assertEqual(self.product.discount_percent, 0)

    def test_current_price_with_sale(self):
        self.product.sale_price = Decimal("750")
        self.assertEqual(self.product.current_price, Decimal("750"))
        self.assertTrue(self.product.on_sale)
        self.assertEqual(self.product.discount_percent, 25)

    def test_sale_price_above_price_is_ignored(self):
        self.product.sale_price = Decimal("1200")
        self.assertEqual(self.product.current_price, Decimal("1000"))
        self.assertFalse(self.product.on_sale)

    def test_stock_is_summed_across_sizes(self):
        ProductVariant.objects.create(product=self.product, size="38", stock=3)
        ProductVariant.objects.create(product=self.product, size="39", stock=4)
        self.assertEqual(self.product.total_stock, 7)
        self.assertTrue(self.product.in_stock)

    def test_sizes_sort_numerically_with_one_size_first(self):
        for size in ["40", "37", "OS", "38"]:
            ProductVariant.objects.create(product=self.product, size=size, stock=1)
        self.assertEqual(
            [v.size for v in self.product.variants.all()], ["OS", "37", "38", "40"]
        )


class GoldProductTests(TestCase):
    def test_gold_attributes_drive_the_gold_display(self):
        category = Category.objects.create(name="Gold")
        brand = Brand.objects.create(name="Habib Jewels", kind=Brand.Kind.GOLD)
        plain = Product.objects.create(
            category=category, name="Plain Ring", price=Decimal("1000")
        )
        gold = Product.objects.create(
            category=category,
            brand=brand,
            name="22K Bangle",
            price=Decimal("120000"),
            karat="22K",
            weight_grams=Decimal("10.00"),
        )
        self.assertFalse(plain.is_gold)
        self.assertIsNone(plain.price_per_gram)
        self.assertTrue(gold.is_gold)
        self.assertEqual(gold.price_per_gram, Decimal("12000.00"))

    def test_brand_initials_for_the_brand_cards(self):
        self.assertEqual(Brand.objects.create(name="Charles & Keith").initials, "CK")
        self.assertEqual(Brand.objects.create(name="Dior").initials, "DI")
        self.assertEqual(Brand.objects.create(name="Kate Spade").initials, "KS")


class BrandSectionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bags = Category.objects.create(name="Bags")
        cls.gold_cat = Category.objects.create(name="Gold")
        cls.fashion = Brand.objects.create(name="Kate Spade", kind=Brand.Kind.FASHION)
        cls.jeweller = Brand.objects.create(name="Habib Jewels", kind=Brand.Kind.GOLD)
        cls.tote = Product.objects.create(
            category=cls.bags, brand=cls.fashion, name="Madison Tote",
            price=Decimal("18500"),
        )
        ProductVariant.objects.create(product=cls.tote, size="OS", stock=3)
        cls.bangle = Product.objects.create(
            category=cls.gold_cat, brand=cls.jeweller, name="22K Bangle",
            price=Decimal("165000"), karat="22K", weight_grams=Decimal("12.00"),
        )
        ProductVariant.objects.create(product=cls.bangle, size="OS", stock=1)

    def test_brand_index_splits_fashion_from_gold(self):
        response = self.client.get(reverse("store:brands"))
        self.assertContains(response, "Kate Spade")
        self.assertContains(response, "Habib Jewels")
        self.assertEqual(
            [b.name for b in response.context["fashion_brands"]], ["Kate Spade"]
        )
        self.assertEqual(
            [b.name for b in response.context["gold_brands"]], ["Habib Jewels"]
        )

    def test_brand_page_lists_only_that_brand(self):
        response = self.client.get(self.fashion.get_absolute_url())
        self.assertContains(response, "Madison Tote")
        self.assertNotContains(response, "22K Bangle")

    def test_gold_page_lists_only_gold(self):
        response = self.client.get(reverse("store:gold"))
        self.assertContains(response, "22K Bangle")
        self.assertNotContains(response, "Madison Tote")

    def test_search_matches_brand_name(self):
        response = self.client.get(reverse("store:catalog"), {"q": "kate spade"})
        self.assertContains(response, "Madison Tote")

    def test_inactive_brand_page_is_gone(self):
        self.fashion.is_active = False
        self.fashion.save()
        self.assertEqual(
            self.client.get(self.fashion.get_absolute_url()).status_code, 404
        )


class CatalogViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(name="Bags")
        cls.product = Product.objects.create(
            category=cls.category, name="Warm Hoodie", price=Decimal("2000")
        )
        ProductVariant.objects.create(product=cls.product, size="OS", stock=5)

    def test_catalog_lists_active_products(self):
        response = self.client.get(reverse("store:catalog"))
        self.assertContains(response, "Warm Hoodie")

    def test_inactive_product_is_hidden(self):
        self.product.is_active = False
        self.product.save()
        response = self.client.get(reverse("store:catalog"))
        self.assertNotContains(response, "Warm Hoodie")
        self.assertEqual(
            self.client.get(self.product.get_absolute_url()).status_code, 404
        )

    def test_search_matches_name(self):
        response = self.client.get(reverse("store:catalog"), {"q": "hoodie"})
        self.assertContains(response, "Warm Hoodie")

    def test_search_with_no_match(self):
        response = self.client.get(reverse("store:catalog"), {"q": "umbrella"})
        self.assertContains(response, "Nothing in stock here")

    def test_unknown_sort_falls_back(self):
        response = self.client.get(reverse("store:catalog"), {"sort": "../etc"})
        self.assertEqual(response.status_code, 200)

    def test_product_detail_renders_the_buy_form(self):
        response = self.client.get(self.product.get_absolute_url())
        self.assertContains(response, "Add to cart")


class SizeFilterTests(TestCase):
    """The size filter belongs only where sizes are a real choice."""

    @classmethod
    def setUpTestData(cls):
        cls.bags = Category.objects.create(name="Bags")
        cls.shoes = Category.objects.create(name="Shoes")

        tote = Product.objects.create(
            category=cls.bags, name="Saffiano Tote", price=Decimal("1200")
        )
        ProductVariant.objects.create(product=tote, size="OS", stock=3)

        cls.pump = Product.objects.create(
            category=cls.shoes, name="Pointed Pump", price=Decimal("400")
        )
        ProductVariant.objects.create(product=cls.pump, size="38", stock=2)
        ProductVariant.objects.create(product=cls.pump, size="39", stock=0)

    def test_one_size_section_hides_the_filter(self):
        response = self.client.get(self.bags.get_absolute_url())
        self.assertEqual(response.context["sizes"], [])
        self.assertNotContains(response, 'id="size"')

    def test_sized_section_shows_only_sizes_in_stock(self):
        response = self.client.get(self.shoes.get_absolute_url())
        self.assertEqual(response.context["sizes"], [("38", "EU 38")])
        self.assertContains(response, 'id="size"')

    def test_filtering_by_size_narrows_the_listing(self):
        response = self.client.get(self.shoes.get_absolute_url(), {"size": "38"})
        self.assertContains(response, "Pointed Pump")
        self.assertEqual(response.context["size"], "38")

    def test_size_the_section_cannot_offer_is_ignored(self):
        """A stale ?size= from another section must not empty the grid."""
        response = self.client.get(self.bags.get_absolute_url(), {"size": "38"})
        self.assertContains(response, "Saffiano Tote")
        self.assertEqual(response.context["size"], "")


class CartNamingTests(TestCase):
    """The cart is called a cart, and the old /bag/ links still land."""

    def test_cart_lives_at_cart(self):
        self.assertEqual(reverse("cart:detail"), "/cart/")

    def test_old_bag_url_redirects(self):
        response = self.client.get("/bag/")
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], "/cart/")

    def test_header_says_cart(self):
        response = self.client.get(reverse("store:catalog"))
        self.assertContains(response, "Cart")
        self.assertNotContains(response, ">Bag<")


class SalePageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(name="Bags")

        def make(name, price, sale=None):
            product = Product.objects.create(
                category=cls.category,
                name=name,
                price=Decimal(price),
                sale_price=Decimal(sale) if sale else None,
            )
            ProductVariant.objects.create(product=product, size="OS", stock=2)
            return product

        cls.big = make("Big Saving Tote", "10000", "7000")   # saves 3000
        cls.small = make("Small Saving Clutch", "5000", "4500")  # saves 500
        cls.plain = make("Full Price Purse", "6000")
        # A sale price that is not actually a discount must not count.
        cls.fake = make("Not Really Reduced", "3000", "3000")

    def test_sale_page_lists_only_real_discounts(self):
        response = self.client.get(reverse("store:sale"))
        self.assertContains(response, "Big Saving Tote")
        self.assertContains(response, "Small Saving Clutch")
        self.assertNotContains(response, "Full Price Purse")
        self.assertNotContains(response, "Not Really Reduced")

    def test_landing_rail_orders_by_biggest_saving(self):
        rail = self.client.get(reverse("store:catalog")).context["home_sale"]
        self.assertEqual(
            [p.name for p in rail], ["Big Saving Tote", "Small Saving Clutch"]
        )

    def test_landing_shows_the_sale_section(self):
        response = self.client.get(reverse("store:catalog"))
        self.assertContains(response, "On sale now")
        self.assertEqual(response.context["home_sale_count"], 2)

    def test_sale_section_hidden_when_nothing_is_reduced(self):
        Product.objects.update(sale_price=None)
        response = self.client.get(reverse("store:catalog"))
        self.assertNotContains(response, "On sale now")
        self.assertEqual(response.context["home_sale"], [])


class LandingPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bags = Category.objects.create(name="Bags")
        cls.empty = Category.objects.create(name="Nothing Here")
        brand = Brand.objects.create(name="Kate Spade")
        product = Product.objects.create(
            category=cls.bags, brand=brand, name="Saffiano Tote", price=Decimal("1200")
        )
        ProductVariant.objects.create(product=product, size="OS", stock=3)

    def test_landing_has_the_new_sections(self):
        response = self.client.get(reverse("store:catalog"))
        for heading in [
            "Cash on delivery",
            "Shop by category",
            "The gold counter",
            "Shop by brand",
        ]:
            self.assertContains(response, heading)

    def test_category_tiles_skip_empty_categories(self):
        rows = self.client.get(reverse("store:catalog")).context["home_categories"]
        self.assertEqual([r["category"].name for r in rows], ["Bags"])

    def test_category_tile_carries_a_count(self):
        rows = self.client.get(reverse("store:catalog")).context["home_categories"]
        self.assertEqual(rows[0]["category"].product_count, 1)

    def test_sections_are_absent_on_a_category_page(self):
        """The rails belong to the landing page only."""
        response = self.client.get(self.bags.get_absolute_url())
        self.assertNotContains(response, "Shop by category")
        self.assertNotIn("home_categories", response.context)


class EmptyCatalogueTests(TestCase):
    """A shop with no stock yet should read as "nothing added", not broken.

    This is the state a fresh deploy lands in before DATABASE_URL points at
    a seeded database, so it needs to render without empty headings.
    """

    def test_landing_page_renders_with_no_products(self):
        response = self.client.get(reverse("store:catalog"))
        self.assertEqual(response.status_code, 200)

    def test_no_empty_category_heading(self):
        response = self.client.get(reverse("store:catalog"))
        self.assertNotContains(response, "Shop by category")

    def test_no_zero_counts_shown(self):
        response = self.client.get(reverse("store:catalog"))
        self.assertNotContains(response, "0 items in stock")
        self.assertNotContains(response, "0 labels")
        self.assertContains(response, "New stock is being added")

    def test_sale_and_featured_rails_absent(self):
        response = self.client.get(reverse("store:catalog"))
        self.assertNotContains(response, "On sale now")
        self.assertNotContains(response, "Featured picks")

