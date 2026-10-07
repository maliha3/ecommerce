import secrets
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Order(models.Model):
    """A customer order paid by cash on delivery or a manual wallet transfer.

    No payment gateway is involved. For bKash/Nagad the customer sends money
    themselves and types the transaction ID here; the shop owner verifies it
    in the admin and flips `payment_status` to Verified.
    """

    class Payment(models.TextChoices):
        COD = "cod", "Cash on Delivery"
        BKASH = "bkash", "bKash (manual transfer)"
        NAGAD = "nagad", "Nagad (manual transfer)"

    class PaymentStatus(models.TextChoices):
        UNPAID = "unpaid", "Unpaid (COD)"
        AWAITING = "awaiting", "Awaiting verification"
        VERIFIED = "verified", "Verified"
        REJECTED = "rejected", "Rejected / not found"

    class Status(models.TextChoices):
        NEW = "new", "New"
        CONFIRMED = "confirmed", "Confirmed"
        PACKED = "packed", "Packed"
        SHIPPED = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    class Area(models.TextChoices):
        DHAKA = "dhaka", "Inside Dhaka"
        OUTSIDE = "outside", "Outside Dhaka"

    order_number = models.CharField(max_length=20, unique=True, editable=False)

    # -- customer -------------------------------------------------------
    full_name = models.CharField("full name", max_length=120)
    phone = models.CharField("phone number", max_length=20)
    email = models.EmailField(blank=True)
    address = models.TextField("delivery address")
    city = models.CharField(max_length=80)
    area = models.CharField(
        max_length=10, choices=Area.choices, default=Area.DHAKA, help_text="Sets the delivery charge."
    )
    note = models.TextField("order note", blank=True)

    # -- payment --------------------------------------------------------
    payment_method = models.CharField(
        max_length=10, choices=Payment.choices, default=Payment.COD
    )
    transaction_id = models.CharField(
        max_length=60,
        blank=True,
        help_text="The bKash/Nagad TrxID the customer submitted. Empty for COD.",
    )
    sender_number = models.CharField(
        max_length=20, blank=True, help_text="The wallet number the money came from."
    )
    payment_status = models.CharField(
        max_length=10, choices=PaymentStatus.choices, default=PaymentStatus.UNPAID
    )

    # -- fulfilment -----------------------------------------------------
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.NEW)
    delivery_charge = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created"]
        indexes = [
            models.Index(fields=["-created"]),
            models.Index(fields=["status"]),
            models.Index(fields=["order_number"]),
        ]

    def __str__(self):
        return self.order_number or f"Order {self.pk}"

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = self._new_order_number()
        if self.payment_method == self.Payment.COD:
            if self.payment_status == self.PaymentStatus.AWAITING:
                self.payment_status = self.PaymentStatus.UNPAID
        elif self.payment_status == self.PaymentStatus.UNPAID:
            self.payment_status = self.PaymentStatus.AWAITING
        super().save(*args, **kwargs)

    @staticmethod
    def _new_order_number():
        # Short, unguessable, and safe to read out over the phone.
        return "TC-" + secrets.token_hex(3).upper()

    def clean(self):
        """The one place the manual-transfer rules live.

        Enforced for the checkout form and the admin alike, so an order can
        never be saved as a wallet transfer without a TrxID to check.
        """
        if not self.is_manual_transfer:
            return

        errors = {}
        trx = (self.transaction_id or "").strip()
        if not trx:
            errors["transaction_id"] = (
                "Please send the payment first, then enter the TrxID from the "
                "confirmation SMS."
            )
        elif len(trx) < 6:
            errors["transaction_id"] = "That TrxID looks too short."

        if not (self.sender_number or "").strip():
            errors["sender_number"] = (
                "Tell us which number you sent the money from."
            )

        if errors:
            raise ValidationError(errors)

    @property
    def is_manual_transfer(self) -> bool:
        return self.payment_method in {self.Payment.BKASH, self.Payment.NAGAD}

    @property
    def subtotal(self) -> Decimal:
        return sum((item.cost for item in self.items.all()), Decimal("0"))

    @property
    def total(self) -> Decimal:
        return self.subtotal + (self.delivery_charge or Decimal("0"))

    @property
    def item_count(self) -> int:
        return sum(item.quantity for item in self.items.all())

    def charge_for_area(self) -> Decimal:
        fee = (
            settings.DELIVERY_CHARGE_DHAKA
            if self.area == self.Area.DHAKA
            else settings.DELIVERY_CHARGE_OUTSIDE
        )
        return Decimal(fee)


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name="items", on_delete=models.CASCADE)
    variant = models.ForeignKey(
        "store.ProductVariant",
        related_name="order_items",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    # Copied at purchase time so the order still reads correctly after the
    # product is renamed, repriced, or deleted.
    product_name = models.CharField(max_length=200)
    size = models.CharField(max_length=20, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.quantity} x {self.product_name} ({self.size})"

    @property
    def cost(self) -> Decimal:
        return self.price * self.quantity
