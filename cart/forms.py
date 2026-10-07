from django import forms

from store.models import ProductVariant


class AddToCartForm(forms.Form):
    """Posted from the product page and the cart's quantity boxes."""

    variant = forms.ModelChoiceField(queryset=ProductVariant.objects.none())
    quantity = forms.IntegerField(min_value=1, max_value=20, initial=1)
    # True from the cart page (set the quantity), False from the product page (add to it).
    override = forms.BooleanField(required=False, initial=False, widget=forms.HiddenInput())

    def __init__(self, *args, product=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = ProductVariant.objects.filter(stock__gt=0)
        if product is not None:
            qs = qs.filter(product=product)
        self.fields["variant"].queryset = qs
        self.fields["variant"].error_messages["invalid_choice"] = (
            "That size is sold out. Please pick another."
        )
