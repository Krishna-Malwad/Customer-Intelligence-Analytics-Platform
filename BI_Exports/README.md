# Power BI — Customer Intelligence Dashboards

## 1. Import the data

Import every CSV in `PowerBI/data/` into Power BI Desktop
(`Get Data -> Text/CSV`). These are the SAME cleaned tables produced by
`Python/etl_pipeline.py`, exported for direct use so Power BI's numbers
always match the Python/SQL numbers exactly.

| File | Role |
|---|---|
| `orders.csv` | Fact — order header |
| `order_items.csv` | Fact — line items (use for revenue) |
| `order_payments.csv` | Fact — payments |
| `order_reviews.csv` | Fact — reviews |
| `order_value_fact.csv` | Pre-aggregated: one row per order with total value + item count (fastest to build KPI cards from) |
| `customers.csv` | Dimension |
| `sellers.csv` | Dimension |
| `products.csv` | Dimension |
| `category_translation.csv` | Dimension (English category names) |
| `geolocation.csv` | Dimension (one row per zip prefix — for maps) |

## 2. Data model (star schema)

Build these relationships in **Model view** (Manage Relationships):

```
customers[customer_id]  1 ──< many  orders[customer_id]
orders[order_id]        1 ──< many  order_items[order_id]
orders[order_id]        1 ──< many  order_payments[order_id]
orders[order_id]        1 ──< many  order_reviews[order_id]
orders[order_id]        1 ──< 1     order_value_fact[order_id]
products[product_id]    1 ──< many  order_items[product_id]
sellers[seller_id]      1 ──< many  order_items[seller_id]
products[product_category_name] many ──< 1  category_translation[product_category_name]
customers[customer_zip_code_prefix] many ──< 1  geolocation[geolocation_zip_code_prefix]
```

Also add a **Date table** (Modeling -> New Table):
```dax
DateTable = CALENDAR(DATE(2016,1,1), DATE(2018,12,31))
Year = YEAR(DateTable[Date])
MonthName = FORMAT(DateTable[Date], "MMM YYYY")
```
Relate `DateTable[Date]` (1) → `orders[order_purchase_timestamp]` (many).
Use this table for all time-intelligence measures instead of the raw
timestamp column directly.

## 3. Core DAX measures (create in a dedicated "Measures" table)

```dax
Total Revenue = SUM(order_items[price])

Total Orders = DISTINCTCOUNT(orders[order_id])

Average Order Value = DIVIDE([Total Revenue], [Total Orders])

Total Customers = DISTINCTCOUNT(customers[customer_unique_id])

Repeat Customers =
VAR OrdersPerCustomer =
    ADDCOLUMNS(
        VALUES(customers[customer_unique_id]),
        "OrderCount", CALCULATE(DISTINCTCOUNT(orders[order_id]))
    )
RETURN COUNTROWS(FILTER(OrdersPerCustomer, [OrderCount] > 1))

Repeat Customer Rate % = DIVIDE([Repeat Customers], [Total Customers]) * 100

Avg Delivery Days =
AVERAGEX(
    FILTER(orders, orders[order_status] = "delivered"),
    DATEDIFF(orders[order_purchase_timestamp], orders[order_delivered_customer_date], DAY)
)

Late Deliveries =
CALCULATE(
    COUNTROWS(orders),
    orders[order_status] = "delivered",
    orders[order_delivered_customer_date] > orders[order_estimated_delivery_date]
)

Late Delivery Rate % =
DIVIDE([Late Deliveries], CALCULATE(COUNTROWS(orders), orders[order_status]="delivered")) * 100

Average Review Score = AVERAGE(order_reviews[review_score])

5-Star Rate % =
DIVIDE(
    CALCULATE(COUNTROWS(order_reviews), order_reviews[review_score] = 5),
    COUNTROWS(order_reviews)
) * 100

Revenue MoM % =
VAR CurrentRev = [Total Revenue]
VAR PriorRev = CALCULATE([Total Revenue], DATEADD(DateTable[Date], -1, MONTH))
RETURN DIVIDE(CurrentRev - PriorRev, PriorRev) * 100
```

## 4. Dashboard build spec

### Dashboard 1 — Executive Overview
- KPI cards: `[Total Revenue]`, `[Total Orders]`, `[Total Customers]`, `[Average Order Value]`
- Line chart: Revenue by Month (`DateTable[MonthName]` on axis, `[Total Revenue]` on values)
- Card + sparkline: `[Revenue MoM %]`

### Dashboard 2 — Customer Intelligence
- Card: `[Total Customers]`, `[Repeat Customer Rate %]`
- Map (Bing/ArcGIS map visual): customers by state, using `geolocation[geolocation_lat/lng]`
- Bar chart: Customers by `customers[customer_state]`
- Table: RFM segments — import `Machine_Learning/ml_output/customer_segments.csv` (from Phase 6) as an additional table, relate on `customer_unique_id`, and build a donut chart of `segment_label` counts

### Dashboard 3 — Product Performance
- Bar chart: Top 10 products by `[Total Revenue]` (filter `order_items[product_id]`, sort descending)
- Bar chart: Top 10 categories by revenue (via `category_translation[product_category_name_english]`)
- Treemap: revenue share by category

### Dashboard 4 — Delivery Performance
- KPI cards: `[Avg Delivery Days]`, `[Late Delivery Rate %]`
- Bar chart: Late Delivery Rate % by `customers[customer_state]`
- Table: Seller performance — group by `sellers[seller_id]`, measures `[Avg Delivery Days]` and `[Late Delivery Rate %]` filtered to that seller's items

### Dashboard 5 — Customer Satisfaction
- KPI cards: `[Average Review Score]`, `[5-Star Rate %]`
- Column chart: review score distribution (1-5) — `order_reviews[review_score]` on axis, count on values
- Line chart: `[Average Review Score]` by month
- Bar chart: lowest-scoring categories (drill from Dashboard 3)

## 5. Why this structure

- **Star schema, not one flat table** — keeps the model performant (Power BI's VertiPaq engine is optimized for star schemas) and keeps filter propagation correct: filtering by `customer_state` correctly cascades to orders → items → revenue.
- **`order_value_fact.csv` exists as a convenience/performance table** for the Executive Overview page, so simple KPI cards don't need to scan the larger `order_items` table.
- **All numbers trace back to the same cleaned data** used in SQL and Python — if a stakeholder asks "does this match the database?", the answer is always yes, because every layer reads from the identical `transform()` output.


> **PBIX note:** The original Power BI `.pbix` binary was not included in either uploaded source ZIP, so it could not be restored into this archive. The Power BI data exports and documentation in this folder are preserved.
