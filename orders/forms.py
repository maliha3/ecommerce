from django import forms

from .models import Order

INPUT = (
    "w-full rounded-lg border border-neutral-300 bg-white px-3 py-2.5 text-sm "
    "text-neutral-900 placeholder-neutral-400 focus:border-neutral-900 "
    "focus:outline-none focus:ring-1 focus:ring-neutral-900"
)


class CheckoutForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = [
            "full_name",
            "phone",
            "email",
            "address",
            "city",
            "area",
            "note",
            "payment_method",
            "sender_number",
            "transaction_id",
        ]
        widgets = {
            "full_name": forms.TextInput(attrs={"placeholder": "Your full name"}),
            "phone": forms.TextInput(attrs={"placeholder": "01XXXXXXXXX"}),
            "email": forms.EmailInput(attrs={"placeholder": "Optional"}),
            "address": forms.Textarea(
                attrs={"rows": 3, "placeholder": "House, road, area"}
            ),
            "city": forms.TextInput(attrs={"placeholder": "Dhaka"}),
            "note": forms.Textarea(
                attrs={"rows": 2, "placeholder": "Anything we should know (optional)"}
            ),
            "payment_method": forms.RadioSelect(),
            "sender_number": forms.TextInput(
                attrs={"placeholder": "Number you sent from"}
            ),
            "transaction_id": forms.TextInput(attrs={"placeholder": "e.g. 9F2K7XQ1AB"}),
        }
        labels = {
            "area": "Delivery area",
            "note": "Order note",
            "transaction_id": "Transaction ID (TrxID)",
            "sender_number": "Your bKash/Nagad number",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].required = False
        for name, field in self.fields.items():
            if name == "payment_method":
                continue
            field.widget.attrs.setdefault("class", INPUT)

    def clean(self):
        """Drop stray wallet fields on a COD order.

        The TrxID rules themselves live on Order.clean(), which Django runs
        for this form and for the admin, so there is only one copy of them.
        """
        cleaned = super().clean()
        if cleaned.get("payment_method") == Order.Payment.COD:
            cleaned["transaction_id"] = ""
            cleaned["sender_number"] = ""
        return cleaned
