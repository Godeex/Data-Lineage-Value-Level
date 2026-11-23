SELECT
  c.customer_id,
  c.name,
  CASE
    WHEN SUM(o.amount) > 200 THEN 'high'
    WHEN SUM(o.amount) > 50 THEN 'mid'
    ELSE 'low'
  END AS segment
FROM {{ ref('stg_orders') }} AS o
JOIN {{ ref('stg_customers') }} AS c ON o.customer_id = c.customer_id
GROUP BY c.customer_id, c.name
