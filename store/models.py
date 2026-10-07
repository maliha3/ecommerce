from decimal import Decimal

from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class TimeStamped(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Category(TimeStamped):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.CharField(max_length=250, blank=True)
    is_active = models.BooleanField(
        default=True, help_text="Untick to hide this category from the shop."
    )
    sort_order = models.PositiveIntegerField(
        default=0, help_text="Lower numbers appear first in the menu."
    )

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("store:category", args=[self.slug])


class Brand(TimeStamped):
    """A label we stock. Gold jewellers are kept apart from fashion houses
    because they are browsed differently — by karat and weight, not by size.
    """

    class Kind(models.TextChoices):
        FASHION = "fashion", "Fashion & lifestyle"
        GOLD = "gold", "Gold jeweller"

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.FASHION)
    country = models.CharField(
        max_length=60, blank=True, help_text="Where the label is from, e.g. France."
    )
    description = models.CharField(max_length=250, blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(
        default=0, help_text="Lower numbers appear first."
    )

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("store:brand", args=[self.slug])

    @property
    def initials(self) -> str:
        """Two-letter mark for the brand cards, since we ship no logos."""
        words = [w for w in self.name.replace("&", " ").split() if w]
        if len(words) == 1:
            return words[0][:2].upper()
        return (words[0][0] + words[1][0]).upper()


class Product(TimeStamped):
    category = models.ForeignKey(
        Category, related_name="products", on_delete=models.PROTECT
    )
    brand = models.ForeignKey(
        Brand,
        related_name="products",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        help_text="Leave blank for unbranded stock.",
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField(
        blank=True, help_text="Fabric, fit, care instructions — shown on the product page."
    )
    price = models.DecimalField(
        max_digits=10, decimal_places=2, help_text="Regular price."
    )
    sale_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Optional. Leave blank when the item is not discounted.",
    )
    image = models.ImageField(
        upload_to="products/",
        blank=True,
        help_text="Square images look best. Uploaded straight to Cloudinary.",
    )
    is_active = models.BooleanField(
        default=True, help_text="Untick to take this product off the shop."
    )
    is_featured = models.BooleanField(
        default=False, help_text="Featured products show on the home page first."
    )

    # Gold-only attributes. Blank for everything else; the product page shows
    # them when they are filled in.
    karat = models.CharField(
        max_length=6,
        blank=True,
        choices=[("18K", "18K"), ("21K", "21K"), ("22K", "22K"), ("24K", "24K")],
        help_text="Gold items only.",
    )
    weight_grams = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Gold items only, in grams.",
    )

    class Meta:
        ordering = ["-is_featured", "-created"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["-created"]),
            models.Index(fields=["is_active", "is_featured"]),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:220]
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("store:product_detail", args=[self.slug])

    @property
    def is_gold(self) -> bool:
        return bool(self.karat)

    @property
    def price_per_gram(self):
        """Useful on gold, where buyers compare the making charge."""
        if not self.weight_grams:
            return None
        return (self.current_price / self.weight_grams).quantize(Decimal("0.01"))

    @property
    def current_price(self) -> Decimal:
        """What the customer is actually charged."""
        if self.sale_price is not None and self.sale_price < self.price:
            return self.sale_price
        return self.price

    @property
    def on_sale(self) -> bool:
        return self.current_price != self.price

    @property
    def discount_percent(self) -> int:
        if not self.on_sale:
            return 0
        return int(round((1 - self.current_price / self.price) * 100))

    @property
    def total_stock(self) -> int:
        return sum(v.stock for v in self.variants.all())

    @property
    def in_stock(self) -> bool:
        return self.is_active and self.total_stock > 0

    def available_variants(self):
        return self.variants.filter(stock__gt=0)


class ProductVariant(models.Model):
    """One size of one product, with its own stock count.

    Clothing sells per size, so stock lives here rather than on Product.
    """

    class Size(models.TextChoices):
        ONE_SIZE = "OS", "One size"
        EU35 = "35", "EU 35"
        EU36 = "36", "EU 36"
        EU37 = "37", "EU 37"
        EU38 = "38", "EU 38"
        EU39 = "39", "EU 39"
        EU40 = "40", "EU 40"
        EU41 = "41", "EU 41"
        EU42 = "42", "EU 42"

    # One size first, then shoe sizes in numeric order.
    SIZE_ORDER = {
        s: i
        for i, s in enumerate(
            ["OS", "35", "36", "37", "38", "39", "40", "41", "42"]
        )
    }

    product = models.ForeignKey(
        Product, related_name="variants", on_delete=models.CASCADE
    )
    size = models.CharField(max_length=4, choices=Size.choices)
    stock = models.PositiveIntegerField(default=0, help_text="Units on hand.")
    sku = models.CharField(max_length=60, blank=True, help_text="Optional internal code.")
    sort_order = models.PositiveSmallIntegerField(default=0, editable=False)

    class Meta:
        # One row per size per product, so stock cannot be split in two places.
        constraints = [
            models.UniqueConstraint(
                fields=["product", "size"], name="unique_size_per_product"
            )
        ]
        ordering = ["sort_order", "size"]

    def __str__(self):
        return f"{self.product.name} - {self.get_size_display()}"

    def save(self, *args, **kwargs):
        self.sort_order = self.SIZE_ORDER.get(self.size, 99)
        super().save(*args, **kwargs)

    @property
    def in_stock(self) -> bool:
        return self.stock > 0

    @property
    def price(self) -> Decimal:
        return self.product.current_price
