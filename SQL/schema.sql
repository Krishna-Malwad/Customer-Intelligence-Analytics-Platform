-- =====================================================================
-- CUSTOMER_INTELLIGENCE  |  PRODUCTION LAYER
-- =====================================================================
-- Purpose:
--   Clean, typed, constrained tables that the ETL pipeline (validation.sql
--   / Python pipeline) loads FROM the *_raw staging tables. All analytics,
--   BI, ML, and GenAI layers read from HERE, never from staging.
--
-- Design decisions (documented so they can be defended in an interview):
--
-- 1) customers.customer_id is the PK because it is unique per order-row
--    in the source data. customer_unique_id is kept as a non-unique
--    attribute (it repeats for returning shoppers) and is INDEXED, not
--    a key, because repeat-customer analysis groups BY it.
--
-- 2) order_items and order_payments have NO single natural key, so we
--    use COMPOSITE PRIMARY KEYS: (order_id, order_item_id) and
--    (order_id, payment_sequential). This mirrors how the source data
--    is actually structured (one order -> many line items / payments).
--
-- 3) order_reviews: profiling showed review_id and order_id are BOTH
--    non-unique in the raw file (duplicate reviews exist). A natural
--    key is unsafe, so we use a SURROGATE key (auto-increment
--    review_pk) and keep review_id/order_id as plain indexed columns.
--
-- 4) geolocation has no reliable natural key and contains heavy
--    duplication (~26% duplicate rows in the raw file). It is loaded
--    as a DEDUPED, AGGREGATED lookup table (one row per zip prefix,
--    average lat/lng) rather than a 1:1 copy of the raw file.
--
-- 5) products.product_category_name is a nullable FK to
--    product_category_translation, because ~1.85% of products have no
--    category, and 2 categories in the product file don't exist in the
--    translation file. We do NOT drop those products; we allow NULL /
--    unmatched categories and handle them explicitly in analysis.
-- =====================================================================

USE customer_intelligence;

SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS order_reviews;
DROP TABLE IF EXISTS order_payments;
DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS product_category_translation;
DROP TABLE IF EXISTS sellers;
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS geolocation;

SET FOREIGN_KEY_CHECKS = 1;

-- ---------------------------------------------------------------------
-- 1. customers  (dimension)
-- ---------------------------------------------------------------------
CREATE TABLE customers (
    customer_id                VARCHAR(64)   NOT NULL,
    customer_unique_id         VARCHAR(64)   NOT NULL,
    customer_zip_code_prefix   INT UNSIGNED  NOT NULL,
    customer_city               VARCHAR(128)  NOT NULL,
    customer_state               CHAR(2)       NOT NULL,
    PRIMARY KEY (customer_id),
    INDEX idx_customer_unique_id (customer_unique_id),
    INDEX idx_customer_zip (customer_zip_code_prefix),
    INDEX idx_customer_state (customer_state)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 2. sellers  (dimension)
-- ---------------------------------------------------------------------
CREATE TABLE sellers (
    seller_id                VARCHAR(64)   NOT NULL,
    seller_zip_code_prefix   INT UNSIGNED  NOT NULL,
    seller_city                VARCHAR(128)  NOT NULL,
    seller_state                CHAR(2)       NOT NULL,
    PRIMARY KEY (seller_id),
    INDEX idx_seller_zip (seller_zip_code_prefix),
    INDEX idx_seller_state (seller_state)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 3. product_category_translation  (dimension / lookup)
-- ---------------------------------------------------------------------
CREATE TABLE product_category_translation (
    product_category_name            VARCHAR(128) NOT NULL,
    product_category_name_english    VARCHAR(128) NOT NULL,
    PRIMARY KEY (product_category_name)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 4. products  (dimension)
-- ---------------------------------------------------------------------
CREATE TABLE products (
    product_id                    VARCHAR(64)   NOT NULL,
    product_category_name          VARCHAR(128)  NULL,
    product_name_lenght            SMALLINT UNSIGNED NULL,
    product_description_lenght     SMALLINT UNSIGNED NULL,
    product_photos_qty             SMALLINT UNSIGNED NULL,
    product_weight_g               DECIMAL(10,2) NULL,
    product_length_cm              DECIMAL(10,2) NULL,
    product_height_cm              DECIMAL(10,2) NULL,
    product_width_cm               DECIMAL(10,2) NULL,
    PRIMARY KEY (product_id),
    INDEX idx_product_category (product_category_name),
    CONSTRAINT fk_products_category
        FOREIGN KEY (product_category_name)
        REFERENCES product_category_translation (product_category_name)
        ON UPDATE CASCADE
        ON DELETE SET NULL
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 5. geolocation  (deduped lookup, one row per zip prefix)
-- ---------------------------------------------------------------------
CREATE TABLE geolocation (
    geolocation_zip_code_prefix   INT UNSIGNED  NOT NULL,
    geolocation_lat                 DECIMAL(10,6) NOT NULL,
    geolocation_lng                 DECIMAL(10,6) NOT NULL,
    geolocation_city                VARCHAR(128)  NOT NULL,
    geolocation_state               CHAR(2)       NOT NULL,
    PRIMARY KEY (geolocation_zip_code_prefix)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 6. orders  (fact - order header)
-- ---------------------------------------------------------------------
CREATE TABLE orders (
    order_id                         VARCHAR(64)  NOT NULL,
    customer_id                      VARCHAR(64)  NOT NULL,
    order_status                     VARCHAR(32)  NOT NULL,
    order_purchase_timestamp         DATETIME     NOT NULL,
    order_approved_at                DATETIME     NULL,
    order_delivered_carrier_date     DATETIME     NULL,
    order_delivered_customer_date    DATETIME     NULL,
    order_estimated_delivery_date    DATETIME     NOT NULL,
    PRIMARY KEY (order_id),
    INDEX idx_orders_customer (customer_id),
    INDEX idx_orders_status (order_status),
    INDEX idx_orders_purchase_ts (order_purchase_timestamp),
    CONSTRAINT fk_orders_customer
        FOREIGN KEY (customer_id)
        REFERENCES customers (customer_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 7. order_items  (fact - line items, COMPOSITE PRIMARY KEY)
-- ---------------------------------------------------------------------
CREATE TABLE order_items (
    order_id                VARCHAR(64)     NOT NULL,
    order_item_id            SMALLINT UNSIGNED NOT NULL,
    product_id               VARCHAR(64)     NOT NULL,
    seller_id                VARCHAR(64)     NOT NULL,
    shipping_limit_date      DATETIME        NOT NULL,
    price                    DECIMAL(10,2)   NOT NULL,
    freight_value            DECIMAL(10,2)   NOT NULL,
    PRIMARY KEY (order_id, order_item_id),
    INDEX idx_items_product (product_id),
    INDEX idx_items_seller (seller_id),
    CONSTRAINT fk_items_order
        FOREIGN KEY (order_id)
        REFERENCES orders (order_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,
    CONSTRAINT fk_items_product
        FOREIGN KEY (product_id)
        REFERENCES products (product_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    CONSTRAINT fk_items_seller
        FOREIGN KEY (seller_id)
        REFERENCES sellers (seller_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    CONSTRAINT chk_items_price_nonneg CHECK (price >= 0),
    CONSTRAINT chk_items_freight_nonneg CHECK (freight_value >= 0)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 8. order_payments  (fact, COMPOSITE PRIMARY KEY)
-- ---------------------------------------------------------------------
CREATE TABLE order_payments (
    order_id                VARCHAR(64)      NOT NULL,
    payment_sequential       SMALLINT UNSIGNED NOT NULL,
    payment_type             VARCHAR(32)      NOT NULL,
    payment_installments      SMALLINT UNSIGNED NOT NULL,
    payment_value             DECIMAL(10,2)    NOT NULL,
    PRIMARY KEY (order_id, payment_sequential),
    INDEX idx_payments_type (payment_type),
    CONSTRAINT fk_payments_order
        FOREIGN KEY (order_id)
        REFERENCES orders (order_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,
    CONSTRAINT chk_payments_value_nonneg CHECK (payment_value >= 0)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 9. order_reviews  (fact, SURROGATE PRIMARY KEY — see design note #3)
-- ---------------------------------------------------------------------
CREATE TABLE order_reviews (
    review_pk                     BIGINT UNSIGNED AUTO_INCREMENT,
    review_id                     VARCHAR(64)  NOT NULL,
    order_id                      VARCHAR(64)  NOT NULL,
    review_score                  TINYINT UNSIGNED NOT NULL,
    review_comment_title           VARCHAR(256) NULL,
    review_comment_message          TEXT        NULL,
    review_creation_date            DATETIME    NOT NULL,
    review_answer_timestamp         DATETIME    NOT NULL,
    PRIMARY KEY (review_pk),
    INDEX idx_reviews_order (order_id),
    INDEX idx_reviews_review_id (review_id),
    INDEX idx_reviews_score (review_score),
    CONSTRAINT fk_reviews_order
        FOREIGN KEY (order_id)
        REFERENCES orders (order_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,
    CONSTRAINT chk_reviews_score_range CHECK (review_score BETWEEN 1 AND 5)
) ENGINE=InnoDB;
