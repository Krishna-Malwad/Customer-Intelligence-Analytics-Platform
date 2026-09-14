# Data Dictionary — Olist Customer Intelligence Platform

Profiled directly from the 9 source CSVs (see `Python/etl_pipeline.py extract()`).

## customers (99,441 rows × 5 cols)
| Column | Type | Nulls | Notes |
|---|---|---|---|
| customer_id | string | 0 | PK. Unique **per order** — a returning shopper gets a new customer_id each order. |
| customer_unique_id | string | 0 | Real persistent shopper identity (96,096 unique values). Use this for repeat-customer analysis. |
| customer_zip_code_prefix | int | 0 | First 5 digits of postal code |
| customer_city | string | 0 | |
| customer_state | string | 0 | 2-letter Brazilian state code |

## orders (99,441 rows × 8 cols)
PK: order_id. FK: customer_id -> customers (100% valid, verified).
| Column | Type | Nulls | Notes |
|---|---|---|---|
| order_status | string | 0 | delivered 96,478 / shipped 1,107 / canceled 625 / unavailable 609 / invoiced 314 / processing 301 / created 5 / approved 2 |
| order_purchase_timestamp | datetime | 0 | |
| order_approved_at | datetime | 160 (0.16%) | Expected null for non-approved orders |
| order_delivered_carrier_date | datetime | 1,783 (1.79%) | Expected null pre-shipment |
| order_delivered_customer_date | datetime | 2,965 (2.98%) | Expected null pre-delivery/canceled |
| order_estimated_delivery_date | datetime | 0 | |

## order_items (112,650 rows × 7 cols)
Composite PK: (order_id, order_item_id). FKs: order_id->orders, product_id->products, seller_id->sellers (all 100% valid, verified).
price and freight_value are decimals, no missing values.

## order_payments (103,886 rows × 5 cols)
Composite PK: (order_id, payment_sequential). FK: order_id->orders (100% valid).
payment_type: credit_card, boleto, voucher, debit_card, not_defined.
More rows than orders because some orders split across multiple payment methods.

## order_reviews (99,224 rows × 7 cols)
No safe natural key — neither review_id (98,410 unique) nor order_id (98,673 unique) is
fully unique in the raw file. Production schema uses a surrogate AUTO_INCREMENT key.
review_comment_title: 88.3% null (optional). review_comment_message: 58.7% null (optional).

## products (32,951 rows × 9 cols)
PK: product_id. product_category_name: 1.85% null. 2 categories
(`pc_gamer`, `portateis_cozinha_e_preparadores_de_alimentos`) have no match in the
translation table — set to NULL in production rather than dropping the product.

## sellers (3,095 rows × 4 cols)
PK: seller_id. Same shape as customers.

## geolocation (1,000,163 raw rows -> 19,015 rows after cleaning)
No natural key in raw data. 261,831 fully duplicate raw rows (26%).
Production table aggregates to one row per zip prefix (avg lat/lng, most frequent city/state).

## product_category_translation (71 rows × 2 cols)
PK: product_category_name. Simple PT->EN lookup, joins to products.

## Entity relationships
```
customers (1) ──< orders (many)
orders (1) ──< order_items (many) >── products (1)
order_items (many) >── sellers (1)
orders (1) ──< order_payments (many)
orders (1) ──< order_reviews (many, effectively ~1)
products (many) >── product_category_translation (1)
customers/sellers (zip) ~~ geolocation (zip, aggregated lookup)
```
