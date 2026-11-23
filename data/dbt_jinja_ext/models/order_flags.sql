SELECT
  order_id,
  {{ m.price_bucket('amount', 100) }} AS flag
FROM {{ ref('stg_orders') }} AS o
