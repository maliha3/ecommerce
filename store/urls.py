from django.urls import path

from . import views

app_name = "store"

urlpatterns = [
    path("", views.catalog, name="catalog"),
    path("brands/", views.brand_index, name="brands"),
    path("gold/", views.gold, name="gold"),
    path("sale/", views.sale, name="sale"),
    path("brand/<slug:slug>/", views.brand_detail, name="brand"),
    path("category/<slug:slug>/", views.catalog, name="category"),
    path("product/<slug:slug>/", views.product_detail, name="product_detail"),
]
