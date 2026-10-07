from django.core.paginator import Paginator
from django.db.models import Count, F, Prefetch, Q, Sum
from django.shortcuts import get_object_or_404, render

from .models import Brand, Category, Product, ProductVariant

PAGE_SIZE = 12

SORT_OPTIONS = {
    "newest": ("-created", "Newest"),
    "price_low": ("price", "Price: low to high"),
    "price_high": ("-price", "Price: high to low"),
    "name": ("name", "Name A-Z"),
}


def _base_queryset():
    """Active products with their in-stock sizes, ready to render."""
    return (
        Product.objects.filter(is_active=True)
        .select_related("category", "brand")
        .prefetch_related(
            Prefetch("variants", queryset=ProductVariant.objects.order_by("sort_order"))
        )
        .annotate(stock_sum=Sum("variants__stock"))
    )


def _sale_queryset():
    """Products with a live discount, biggest saving first.

    `Product.on_sale` is a Python property, so the same rule is expressed in
    SQL here: a sale price that is set and genuinely below the regular price.
    """
    return (
        _base_queryset()
        .filter(sale_price__isnull=False, sale_price__lt=F("price"))
        .annotate(saving=F("price") - F("sale_price"))
        .order_by("-saving")
    )


def _home_sections():
    """The landing-page rails.

    Each one is built from live stock, so a section with nothing in it renders
    as nothing rather than as an empty heading. The per-category lookup is a
    handful of queries against a five-row table; cache it if the menu grows.
    """
    categories = []
    for category in Category.objects.filter(is_active=True).annotate(
        product_count=Count("products", filter=Q(products__is_active=True))
    ):
        if not category.product_count:
            continue
        categories.append(
            {
                "category": category,
                # A tile needs a picture, so borrow one from its best product.
                "cover": (
                    Product.objects.filter(category=category, is_active=True)
                    .exclude(image="")
                    .order_by("-is_featured", "-created")
                    .first()
                ),
            }
        )

    return {
        # Static, but kept beside the other rails so the template stays markup.
        "service_points": [
            ("\U0001F69A", "Cash on delivery", "Anywhere in Bangladesh"),
            ("\U0001F4F1", "bKash / Nagad", "Pay on confirmation"),
            ("\u2708\uFE0F", "Brought in from KL", "Sourced, not resold"),
            ("\U0001F48E", "Hallmarked gold", "Karat and weight stated"),
        ],
        "home_categories": categories,
        "home_sale": list(_sale_queryset()[:4]),
        "home_sale_count": _sale_queryset().count(),
        "home_featured": list(_base_queryset().filter(is_featured=True)[:4]),
        "home_brands": Brand.objects.filter(is_active=True).annotate(
            product_count=Count("products", filter=Q(products__is_active=True))
        )[:8],
    }


def _listing(request, products, **context):
    """Shared search / size filter / sort / pagination for every listing page."""
    query = request.GET.get("q", "").strip()
    if query:
        products = products.filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(category__name__icontains=query)
            | Q(brand__name__icontains=query)
        )

    # Size options come from the stock in this listing, not the whole size
    # enum: the filter then shows up only where sizes mean something (shoes)
    # and never offers a size there is nothing in. One-size rows are skipped
    # because "One size" is not a choice a customer makes. Worked out before
    # the size filter is applied, or picking one size would drop the others
    # from the dropdown and strand the customer on that size.
    labels = dict(ProductVariant.Size.choices)
    available = (
        ProductVariant.objects.filter(product__in=products, stock__gt=0)
        .exclude(size=ProductVariant.Size.ONE_SIZE)
        .values_list("size", flat=True)
        .distinct()
    )
    sizes = [
        (value, labels[value])
        for value in sorted(available, key=lambda v: ProductVariant.SIZE_ORDER.get(v, 99))
    ]

    # Ignore a size that this listing cannot offer, so a stale ?size= carried
    # over from another section does not render an empty grid.
    size = request.GET.get("size", "")
    if size not in dict(sizes):
        size = ""
    if size:
        products = products.filter(variants__size=size, variants__stock__gt=0).distinct()

    sort = request.GET.get("sort") if request.GET.get("sort") in SORT_OPTIONS else "newest"
    products = products.order_by(SORT_OPTIONS[sort][0])

    paginator = Paginator(products, PAGE_SIZE)
    page = paginator.get_page(request.GET.get("page"))

    # Kept so pagination links do not drop the active filters.
    params = request.GET.copy()
    params.pop("page", None)

    context.update(
        {
            "page": page,
            "products": page.object_list,
            "query": query,
            "sort": sort,
            "size": size,
            "sort_options": SORT_OPTIONS,
            "sizes": sizes,
            "total_count": paginator.count,
            "querystring": params.urlencode(),
        }
    )
    return render(request, context.pop("template", "store/catalog.html"), context)


def catalog(request, slug=None):
    """The storefront: everything, or one section."""
    category = None
    products = _base_queryset()

    if slug:
        category = get_object_or_404(Category, slug=slug, is_active=True)
        products = products.filter(category=category)

    is_home = (
        slug is None and not request.GET.get("q") and not request.GET.get("size")
    )
    extra = _home_sections() if is_home else {}

    return _listing(
        request,
        products,
        category=category,
        is_home=is_home,
        **extra,
    )


def brand_index(request):
    """Shop by brand: the labels we carry, split by fashion and gold."""
    brands = (
        Brand.objects.filter(is_active=True)
        .annotate(product_count=Count("products", filter=Q(products__is_active=True)))
    )
    return render(
        request,
        "store/brands.html",
        {
            "fashion_brands": [b for b in brands if b.kind == Brand.Kind.FASHION],
            "gold_brands": [b for b in brands if b.kind == Brand.Kind.GOLD],
        },
    )


def brand_detail(request, slug):
    brand = get_object_or_404(Brand, slug=slug, is_active=True)
    return _listing(request, _base_queryset().filter(brand=brand), brand=brand)


def gold(request):
    """The gold counter, browsed by jeweller rather than by size."""
    products = _base_queryset().filter(karat__gt="")
    return _listing(
        request,
        products,
        is_gold_page=True,
        gold_brands=Brand.objects.filter(
            is_active=True, kind=Brand.Kind.GOLD
        ).annotate(product_count=Count("products", filter=Q(products__is_active=True))),
    )


def sale(request):
    """Everything currently discounted, in one place."""
    return _listing(request, _sale_queryset(), is_sale_page=True)


def product_detail(request, slug):
    product = get_object_or_404(_base_queryset(), slug=slug)
    related = (
        _base_queryset()
        .filter(category=product.category)
        .exclude(pk=product.pk)[:4]
    )
    return render(
        request,
        "store/product_detail.html",
        {
            "product": product,
            "variants": product.variants.all(),
            "related": related,
        },
    )


def page_not_found(request, exception):
    return render(request, "404.html", status=404)
