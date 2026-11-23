SELECT
  order_id,
  amount,
  {{ m.price_bucket('amount', 100) }} AS flag
FROM {{ ref('stg_orders') }} AS o
ORDER BY amount DESC
LIMIT 3
