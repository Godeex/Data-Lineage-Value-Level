WITH base AS (
  SELECT customer_id, amount, refunded
  FROM {{ ref('stg_orders') }}
)
SELECT
  customer_id,
  COUNT(*) AS n,
  SUM(amount) AS total,
  {{ m.price_bucket('SUM(amount)', 150) }} AS bucket
FROM base
GROUP BY customer_id
