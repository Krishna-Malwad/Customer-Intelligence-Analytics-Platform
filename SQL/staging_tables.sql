-- =====================================================================
-- CUSTOMER_INTELLIGENCE  |  STAGING / RAW LAYER
-- =====================================================================
-- Purpose:
--   Land the CSV data exactly as-is, with NO constraints, NO type
--   enforcement beyond basic string/number storage, and NO foreign keys.
--   This layer exists so that a bad row in the source file never blocks
--   a full LOAD DATA import. All cleaning/validation happens afterward
--   in validation.sql, when moving _raw -> production tables.
--
--   Every column here is intentionally VARCHAR/TEXT or a loose numeric
--   type so dirty data (blank strings, malformed dates, stray spaces)
--   can still land without an import failure.
-- =====================================================================

CREATE DATABASE IF NOT EXISTS customer_intelligence
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE customer_intelligence;

-- ---------------------------------------------------------------------
-- customers_raw
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS customers_raw;
CREATE TABLE customers_raw (
    customer_id                VARCHAR(64),
    customer_unique_id         VARCHAR(64),
    customer_zip_code_prefix   VARCHAR(16),
    customer_city               VARCHAR(128),
    customer_state              VARCHAR(8)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- orders_raw
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS orders_raw;
CREATE TABLE orders_raw (
    order_id                        VARCHAR(64),
    customer_id                     VARCHAR(64),
    order_status                    VARCHAR(32),
    order_purchase_timestamp        VARCHAR(32),
    order_approved_at               VARCHAR(32),
    order_delivered_carrier_date    VARCHAR(32),
    order_delivered_customer_date   VARCHAR(32),
    order_estimated_delivery_date   VARCHAR(32)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- order_items_raw
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS order_items_raw;
CREATE TABLE order_items_raw (
    order_id                VARCHAR(64),
    order_item_id            VARCHAR(16),
    product_id               VARCHAR(64),
    seller_id                VARCHAR(64),
    shipping_limit_date      VARCHAR(32),
    price                    VARCHAR(32),
    freight_value            VARCHAR(32)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- order_payments_raw
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS order_payments_raw;
CREATE TABLE order_payments_raw (
    order_id                VARCHAR(64),
    payment_sequential       VARCHAR(16),
    payment_type             VARCHAR(32),
    payment_installments      VARCHAR(16),
    payment_value             VARCHAR(32)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- order_reviews_raw
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS order_reviews_raw;
CREATE TABLE order_reviews_raw (
    review_id                    VARCHAR(64),
    order_id                     VARCHAR(64),
    review_score                 VARCHAR(8),
    review_comment_title          VARCHAR(256),
    review_comment_message        TEXT,
    review_creation_date          VARCHAR(32),
    review_answer_timestamp       VARCHAR(32)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- products_raw
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS products_raw;
CREATE TABLE products_raw (
    product_id                    VARCHAR(64),
    product_category_name          VARCHAR(128),
    product_name_lenght            VARCHAR(16),
    product_description_lenght     VARCHAR(16),
    product_photos_qty             VARCHAR(16),
    product_weight_g               VARCHAR(16),
    product_length_cm              VARCHAR(16),
    product_height_cm              VARCHAR(16),
    product_width_cm               VARCHAR(16)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- sellers_raw
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS sellers_raw;
CREATE TABLE sellers_raw (
    seller_id                 VARCHAR(64),
    seller_zip_code_prefix    VARCHAR(16),
    seller_city                VARCHAR(128),
    seller_state                VARCHAR(8)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- geolocation_raw
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS geolocation_raw;
CREATE TABLE geolocation_raw (
    geolocation_zip_code_prefix   VARCHAR(16),
    geolocation_lat                 VARCHAR(32),
    geolocation_lng                 VARCHAR(32),
    geolocation_city                VARCHAR(128),
    geolocation_state               VARCHAR(8)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- product_category_translation_raw
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS product_category_translation_raw;
CREATE TABLE product_category_translation_raw (
    product_category_name           VARCHAR(128),
    product_category_name_english   VARCHAR(128)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- LOAD DATA EXAMPLES (adjust file path per your environment)
-- ---------------------------------------------------------------------
-- LOAD DATA LOCAL INFILE '/path/olist_customers_dataset.csv'
-- INTO TABLE customers_raw
-- FIELDS TERMINATED BY ',' ENCLOSED BY '"'
-- LINES TERMINATED BY '\n'
-- IGNORE 1 ROWS;
--
-- Repeat the same pattern for each *_raw table using its matching CSV.
