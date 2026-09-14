-- =====================================================================
-- CUSTOMER_INTELLIGENCE  |  PHASE 2: SQL ETL — VALIDATION + LOAD
-- =====================================================================
-- Order of operations in this file:
--   SECTION A: Pre-load validation queries (run these FIRST, read-only,
--              they just report problems — they don't fix anything)
--   SECTION B: Staging -> Production INSERT statements that clean data
--              as part of the load (this is where the actual fixes live)
--   SECTION C: Post-load referential integrity checks
--
-- Load order matters because of foreign keys:
--   customers, sellers, product_category_translation  (no dependencies)
--   -> products (depends on category_translation)
--   -> geolocation (independent, but deduped/aggregated)
--   -> orders (depends on customers)
--   -> order_items (depends on orders, products, sellers)
--   -> order_payments (depends on orders)
--   -> order_reviews (depends on orders)
-- =====================================================================

USE customer_intelligence;

-- =====================================================================
-- SECTION A: PRE-LOAD VALIDATION (reporting only)
-- =====================================================================

-- A1. Duplicate full rows per staging table
SELECT 'customers_raw' AS tbl, COUNT(*) AS dup_rows FROM (
    SELECT customer_id, COUNT(*) c FROM customers_raw GROUP BY customer_id HAVING c > 1
) x
UNION ALL
SELECT 'orders_raw', COUNT(*) FROM (
    SELECT order_id, COUNT(*) c FROM orders_raw GROUP BY order_id HAVING c > 1
) x
UNION ALL
SELECT 'order_items_raw', COUNT(*) FROM (
    SELECT order_id, order_item_id, COUNT(*) c FROM order_items_raw
    GROUP BY order_id, order_item_id HAVING c > 1
) x
UNION ALL
SELECT 'order_payments_raw', COUNT(*) FROM (
    SELECT order_id, payment_sequential, COUNT(*) c FROM order_payments_raw
    GROUP BY order_id, payment_sequential HAVING c > 1
) x
UNION ALL
SELECT 'geolocation_raw full-row duplicates', COUNT(*) FROM (
    SELECT geolocation_zip_code_prefix, geolocation_lat, geolocation_lng,
           geolocation_city, geolocation_state, COUNT(*) c
    FROM geolocation_raw
    GROUP BY 1,2,3,4,5 HAVING c > 1
) x;

-- A2. NULL / blank checks on columns that must never be empty downstream
SELECT
    SUM(customer_id IS NULL OR customer_id = '')               AS null_customer_id,
    SUM(customer_zip_code_prefix IS NULL OR customer_zip_code_prefix = '') AS null_zip
FROM customers_raw;

SELECT
    SUM(order_id IS NULL OR order_id = '')                     AS null_order_id,
    SUM(order_purchase_timestamp IS NULL OR order_purchase_timestamp = '') AS null_purchase_ts,
    SUM(order_status IS NULL OR order_status = '')             AS null_status
FROM orders_raw;

-- A3. Numeric sanity: negative prices / freight / payment values
SELECT COUNT(*) AS negative_price_rows
FROM order_items_raw
WHERE CAST(price AS DECIMAL(10,2)) < 0 OR CAST(freight_value AS DECIMAL(10,2)) < 0;

SELECT COUNT(*) AS negative_payment_rows
FROM order_payments_raw
WHERE CAST(payment_value AS DECIMAL(10,2)) < 0;

-- A4. Date validation: delivered date earlier than purchase date (impossible)
SELECT COUNT(*) AS impossible_delivery_dates
FROM orders_raw
WHERE order_delivered_customer_date IS NOT NULL
  AND order_delivered_customer_date <> ''
  AND STR_TO_DATE(order_delivered_customer_date, '%Y-%m-%d %H:%i:%s')
      < STR_TO_DATE(order_purchase_timestamp, '%Y-%m-%d %H:%i:%s');

-- A5. Referential orphan checks (rows in child staging table with no
--     matching parent — these would violate FK constraints on load)
SELECT COUNT(*) AS orphan_orders_customers
FROM orders_raw o
LEFT JOIN customers_raw c ON o.customer_id = c.customer_id
WHERE c.customer_id IS NULL;

SELECT COUNT(*) AS orphan_items_orders
FROM order_items_raw i
LEFT JOIN orders_raw o ON i.order_id = o.order_id
WHERE o.order_id IS NULL;

-- A6. Category names present in products but missing from translation table
SELECT DISTINCT p.product_category_name
FROM products_raw p
LEFT JOIN product_category_translation_raw t
       ON p.product_category_name = t.product_category_name
WHERE p.product_category_name IS NOT NULL
  AND p.product_category_name <> ''
  AND t.product_category_name IS NULL;

-- =====================================================================
-- SECTION B: STAGING -> PRODUCTION LOAD (cleaning happens here)
-- =====================================================================

-- B1. product_category_translation (load first, no dependencies)
INSERT INTO product_category_translation (product_category_name, product_category_name_english)
SELECT DISTINCT product_category_name, product_category_name_english
FROM product_category_translation_raw
WHERE product_category_name IS NOT NULL AND product_category_name <> '';

-- B2. customers
--   - dedupe on customer_id (PK)
--   - drop rows missing required fields
INSERT INTO customers (customer_id, customer_unique_id, customer_zip_code_prefix,
                        customer_city, customer_state)
SELECT customer_id, customer_unique_id, CAST(customer_zip_code_prefix AS UNSIGNED),
       TRIM(customer_city), TRIM(UPPER(customer_state))
FROM (
    SELECT c.*, ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY customer_id) AS rn
    FROM customers_raw c
    WHERE customer_id IS NOT NULL AND customer_id <> ''
      AND customer_zip_code_prefix REGEXP '^[0-9]+$'
) d
WHERE rn = 1;

-- B3. sellers
INSERT INTO sellers (seller_id, seller_zip_code_prefix, seller_city, seller_state)
SELECT seller_id, CAST(seller_zip_code_prefix AS UNSIGNED),
       TRIM(seller_city), TRIM(UPPER(seller_state))
FROM (
    SELECT s.*, ROW_NUMBER() OVER (PARTITION BY seller_id ORDER BY seller_id) AS rn
    FROM sellers_raw s
    WHERE seller_id IS NOT NULL AND seller_id <> ''
      AND seller_zip_code_prefix REGEXP '^[0-9]+$'
) d
WHERE rn = 1;

-- B4. products
--   - unmatched / missing category becomes NULL (FK allows NULL, see schema.sql note #5)
INSERT INTO products (product_id, product_category_name, product_name_lenght,
                       product_description_lenght, product_photos_qty,
                       product_weight_g, product_length_cm, product_height_cm, product_width_cm)
SELECT
    p.product_id,
    CASE WHEN t.product_category_name IS NULL THEN NULL ELSE p.product_category_name END,
    NULLIF(p.product_name_lenght, ''),
    NULLIF(p.product_description_lenght, ''),
    NULLIF(p.product_photos_qty, ''),
    NULLIF(p.product_weight_g, ''),
    NULLIF(p.product_length_cm, ''),
    NULLIF(p.product_height_cm, ''),
    NULLIF(p.product_width_cm, '')
FROM (
    SELECT r.*, ROW_NUMBER() OVER (PARTITION BY product_id ORDER BY product_id) AS rn
    FROM products_raw r
    WHERE product_id IS NOT NULL AND product_id <> ''
) p
LEFT JOIN product_category_translation t
       ON p.product_category_name = t.product_category_name
WHERE p.rn = 1;

-- B5. geolocation — deduplicate AND aggregate to one row per zip prefix.
--   Strategy: average lat/lng across all raw points for a zip prefix,
--   and take one representative city/state (most frequent) per zip.
INSERT INTO geolocation (geolocation_zip_code_prefix, geolocation_lat, geolocation_lng,
                          geolocation_city, geolocation_state)
SELECT
    g.geolocation_zip_code_prefix,
    avg_pts.avg_lat,
    avg_pts.avg_lng,
    g.geolocation_city,
    g.geolocation_state
FROM (
    SELECT geolocation_zip_code_prefix,
           AVG(CAST(geolocation_lat AS DECIMAL(10,6))) AS avg_lat,
           AVG(CAST(geolocation_lng AS DECIMAL(10,6))) AS avg_lng
    FROM geolocation_raw
    WHERE geolocation_zip_code_prefix REGEXP '^[0-9]+$'
    GROUP BY geolocation_zip_code_prefix
) avg_pts
JOIN (
    SELECT geolocation_zip_code_prefix, geolocation_city, geolocation_state,
           ROW_NUMBER() OVER (
               PARTITION BY geolocation_zip_code_prefix
               ORDER BY COUNT(*) DESC
           ) AS rn
    FROM geolocation_raw
    WHERE geolocation_zip_code_prefix REGEXP '^[0-9]+$'
    GROUP BY geolocation_zip_code_prefix, geolocation_city, geolocation_state
) g
  ON g.geolocation_zip_code_prefix = avg_pts.geolocation_zip_code_prefix AND g.rn = 1;

-- B6. orders
--   - only load rows whose customer_id already exists in production customers
--   - convert string timestamps to DATETIME
INSERT INTO orders (order_id, customer_id, order_status, order_purchase_timestamp,
                     order_approved_at, order_delivered_carrier_date,
                     order_delivered_customer_date, order_estimated_delivery_date)
SELECT
    o.order_id, o.customer_id, o.order_status,
    STR_TO_DATE(o.order_purchase_timestamp, '%Y-%m-%d %H:%i:%s'),
    STR_TO_DATE(NULLIF(o.order_approved_at, ''), '%Y-%m-%d %H:%i:%s'),
    STR_TO_DATE(NULLIF(o.order_delivered_carrier_date, ''), '%Y-%m-%d %H:%i:%s'),
    STR_TO_DATE(NULLIF(o.order_delivered_customer_date, ''), '%Y-%m-%d %H:%i:%s'),
    STR_TO_DATE(o.order_estimated_delivery_date, '%Y-%m-%d %H:%i:%s')
FROM (
    SELECT r.*, ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY order_id) AS rn
    FROM orders_raw r
    WHERE order_id IS NOT NULL AND order_id <> ''
) o
JOIN customers c ON o.customer_id = c.customer_id
WHERE o.rn = 1;

-- B7. order_items
--   - dedupe on composite key, only load if parent order/product/seller exist
INSERT INTO order_items (order_id, order_item_id, product_id, seller_id,
                          shipping_limit_date, price, freight_value)
SELECT i.order_id, CAST(i.order_item_id AS UNSIGNED), i.product_id, i.seller_id,
       STR_TO_DATE(i.shipping_limit_date, '%Y-%m-%d %H:%i:%s'),
       CAST(i.price AS DECIMAL(10,2)), CAST(i.freight_value AS DECIMAL(10,2))
FROM (
    SELECT r.*, ROW_NUMBER() OVER (PARTITION BY order_id, order_item_id ORDER BY order_id) AS rn
    FROM order_items_raw r
    WHERE CAST(price AS DECIMAL(10,2)) >= 0 AND CAST(freight_value AS DECIMAL(10,2)) >= 0
) i
JOIN orders o ON i.order_id = o.order_id
JOIN products p ON i.product_id = p.product_id
JOIN sellers s ON i.seller_id = s.seller_id
WHERE i.rn = 1;

-- B8. order_payments
INSERT INTO order_payments (order_id, payment_sequential, payment_type,
                             payment_installments, payment_value)
SELECT p.order_id, CAST(p.payment_sequential AS UNSIGNED), p.payment_type,
       CAST(p.payment_installments AS UNSIGNED), CAST(p.payment_value AS DECIMAL(10,2))
FROM (
    SELECT r.*, ROW_NUMBER() OVER (PARTITION BY order_id, payment_sequential ORDER BY order_id) AS rn
    FROM order_payments_raw r
    WHERE CAST(payment_value AS DECIMAL(10,2)) >= 0
) p
JOIN orders o ON p.order_id = o.order_id
WHERE p.rn = 1;

-- B9. order_reviews
--   - fully duplicate raw rows are collapsed; near-duplicates keep a
--     surrogate key so nothing is silently dropped
INSERT INTO order_reviews (review_id, order_id, review_score, review_comment_title,
                            review_comment_message, review_creation_date, review_answer_timestamp)
SELECT DISTINCT
    r.review_id, r.order_id, CAST(r.review_score AS UNSIGNED),
    NULLIF(r.review_comment_title, ''), NULLIF(r.review_comment_message, ''),
    STR_TO_DATE(r.review_creation_date, '%Y-%m-%d %H:%i:%s'),
    STR_TO_DATE(r.review_answer_timestamp, '%Y-%m-%d %H:%i:%s')
FROM order_reviews_raw r
JOIN orders o ON r.order_id = o.order_id
WHERE r.review_score REGEXP '^[1-5]$';

-- =====================================================================
-- SECTION C: POST-LOAD INTEGRITY CHECKS (row counts should reconcile)
-- =====================================================================

SELECT 'customers' AS tbl, COUNT(*) AS row_count FROM customers
UNION ALL SELECT 'sellers', COUNT(*) FROM sellers
UNION ALL SELECT 'products', COUNT(*) FROM products
UNION ALL SELECT 'product_category_translation', COUNT(*) FROM product_category_translation
UNION ALL SELECT 'geolocation', COUNT(*) FROM geolocation
UNION ALL SELECT 'orders', COUNT(*) FROM orders
UNION ALL SELECT 'order_items', COUNT(*) FROM order_items
UNION ALL SELECT 'order_payments', COUNT(*) FROM order_payments
UNION ALL SELECT 'order_reviews', COUNT(*) FROM order_reviews;

-- Orphan check post-load — should always return 0 rows given FK constraints,
-- this is a defensive re-check for CI/CD pipelines.
SELECT COUNT(*) AS orphan_items FROM order_items oi
LEFT JOIN orders o ON oi.order_id = o.order_id WHERE o.order_id IS NULL;
