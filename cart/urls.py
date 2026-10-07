from django.urls import path

from . import views

app_name = "cart"

urlpatterns = [
    path("", views.cart_detail, name="detail"),
    path("add/<slug:product_slug>/", views.cart_add, name="add"),
    path("remove/<int:variant_id>/", views.cart_remove, name="remove"),
]
