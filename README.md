# Hello Malaysia — a minimal Django storefront

Branded bags, shoes, jewellery and gold, bought in Malaysia and sold in
Bangladesh. Built to run on **free tiers only**: Render (web), Neon (Postgres),
Cloudinary (images). No payment gateway — orders are paid **cash on delivery**
or by a **manual bKash / Nagad transfer** whose TrxID the owner verifies in the
admin. Prices are in BDT (৳).

## What is here

| Path | What it does |
| --- | --- |
| `config/` | Settings, URLs, WSGI entry point |
| `store/` | `Category`, `Brand`, `Product`, `ProductVariant`; catalogue, brand and gold pages |
| `cart/` | Session-backed bag, keyed by product **and** size |
| `orders/` | `Order`, `OrderItem`, the manual checkout flow |
| `templates/` | Tailwind-via-CDN templates; no build step |
| `store/mockimages.py` | Draws the placeholder product photos |
| `store/management/commands/seed_data.py` | 5 sections, 13 brands, 23 products |
| `build.sh`, `render.yaml` | Render deployment |

### How the shop is organised

Two ways to browse the same stock, which is why `Category` and `Brand` are
separate models rather than one tree:

- **Sections** (`Category`) — Bags, Shoes, Jewellery, Gold, Watches & Tech.
- **Shop by brand** (`Brand`) — at `/brands/`, split into fashion houses and
  gold jewellers, because the two are shopped differently.
- **The gold counter** (`/gold/`) — everything with a karat set, shown with
  weight and a price per gram.

### Design decisions worth knowing

- **Stock lives on `ProductVariant`, not `Product`.** A shoe in EU 38 is a
  different thing to sell than the same shoe in EU 41. Bags, jewellery and gold
  use a single `One size` variant, so one code path covers everything.
- **The cart snapshots the price** when an item is added, so a price edit in the
  admin cannot change what a shopper is mid-way through buying. That matters
  most on gold, where you may reprice daily.
- **Checkout locks variant rows** (`select_for_update`) and decrements stock in
  the same transaction as the order, so two buyers cannot take the same last unit.
- **Order items copy the product name, size and price.** Renaming or deleting a
  product later does not corrupt past orders.
- **Manual-transfer rules live on `Order.clean()`**, so the checkout form *and*
  the admin both refuse a bKash/Nagad order with no TrxID.
- **The confirmation page is session-scoped** — an order number in the URL is not
  enough to read someone else's order.

## About the product photos

`seed_data --images` draws every photo with Pillow (`store/mockimages.py`):
bags, shoes, jewellery, gold and tech, each with a material finish and a soft
shadow. They are illustrations, not photographs.

That is deliberate. Brand catalogue imagery is the brand's copyright, and a
reseller's listings are supposed to show *their own* stock anyway — buyers want
to see the actual bag in the actual box. So: generated placeholders now, and the
owner replaces them from the admin as stock is photographed. Upload a real photo
on any product and it takes over immediately.

Brand names are used plainly to say what is stocked. No logos ship with this
repo.

## Run it locally

Needs Python 3.9+ (3.11 or 3.12 recommended).

```bash
cd django-ecommerce
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # defaults are fine for local work

python manage.py migrate
python manage.py seed_data --images
python manage.py createsuperuser
python manage.py runserver
```

- Storefront: http://127.0.0.1:8000/
- Shop by brand: http://127.0.0.1:8000/brands/
- Gold counter: http://127.0.0.1:8000/gold/
- Admin: http://127.0.0.1:8000/admin/

With no `DATABASE_URL` set it uses SQLite, and with no `CLOUDINARY_URL` it stores
uploads in `./media` — so nothing needs an account until you deploy.

```bash
python manage.py test        # 43 tests
```

## The three free services

### 1. Neon — Postgres

1. Create a project at [neon.tech](https://neon.tech).
2. **Connection Details → Pooled connection**, copy the string.
3. Set it as `DATABASE_URL`. Use the **`-pooler`** host: Render's free dyno opens
   and drops connections constantly and the pooler absorbs that.

> Free Neon branches auto-suspend after inactivity. The first request after a
> sleep takes a few seconds; `conn_health_checks` is on so stale connections are
> recycled rather than erroring.

### 2. Cloudinary — product images

1. Sign up at [cloudinary.com](https://cloudinary.com).
2. **Dashboard → API environment variable**, copy the `cloudinary://...` value.
3. Set it as `CLOUDINARY_URL`.

Uploads go to Cloudinary the moment that variable exists — no code change. The
owner just uses the normal "Choose file" button in the admin.

### 3. Render — hosting

1. Push this folder to GitHub.
2. Render → **New + → Blueprint**, point at the repo (`render.yaml` is read).
3. In the dashboard, fill the values marked `sync: false`:
   `DATABASE_URL`, `CLOUDINARY_URL`, `BKASH_NUMBER`, `NAGAD_NUMBER`, `SHOP_PHONE`.
4. Deploy. `build.sh` installs, runs `collectstatic`, then `migrate`.
5. Shell into the service once: `python manage.py createsuperuser`.

> The free web service sleeps after ~15 minutes idle; the next visitor waits
> roughly 30 seconds for it to wake. That is the trade for £0/month.

## How payment works

No gateway, no card data, no webhook. At checkout the customer picks:

**Cash on Delivery** — `payment_status` is `Unpaid`. They pay the courier.

**bKash / Nagad transfer** — the page shows your merchant number, the customer
sends the money themselves, then enters the **TrxID** from the confirmation SMS
plus the number they sent from. The order saves as `Awaiting verification`.

Then, in the admin:

1. Open **Orders**. The TrxID and sender number are in the list, no clicking.
2. Check the TrxID against your bKash/Nagad statement.
3. Select the order → **Mark payment as verified** (or set it to *Rejected*).
4. Move it along with **Mark as confirmed / shipped / delivered**.

Set your real numbers in `BKASH_NUMBER` and `NAGAD_NUMBER` before going live —
the defaults are placeholders.

## Admin notes for a non-technical owner

- **Products** — "Add product", pick a **brand** and a **section**, set the
  price, upload a photo. Then add a row per size under **Sizes and stock**. For
  a bag or a gold piece, add one row with size *One size*.
- **Gold** — fill in **Karat** and **Weight (grams)** under the collapsed *Gold*
  panel. That alone moves the piece onto the gold counter and shows the price
  per gram.
- **Putting something on sale** — type a *Sale price*. The old price shows struck
  through with a "-25%" badge, worked out automatically. Blank it to end the sale.
- **Restocking** — **Product variants** lists every size of every product with an
  editable stock box, so a stock-take is one page and one Save.
- **Orders** — stock is deducted automatically when an order is placed.
  Cancelling an order in the admin does *not* add it back; adjust stock by hand.

## Things deliberately left out

Customer accounts, coupons, wishlists, email sending, and refunds. Each adds
either a paid service or a surface the owner would have to manage. The models
leave room: `Order` has an `email` field ready for a confirmation mail, and
`OrderItem` keeps a nullable FK to the variant for future reporting.
