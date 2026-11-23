SELECT
  c.country,
  SUM(CASE WHEN o.refunded = 1 THEN 1 ELSE 0 END) AS refunds,
  COUNT(*) AS n,
  {{ m.safe_divide("SUM(CASE WHEN o.refunded = 1 THEN 1 ELSE 0 END)", 'COUNT(*)') }} AS refund_rate
FROM {{ ref('stg_orders') }} AS o
JOIN {{ ref('stg_customers') }} AS c ON o.customer_id = c.customer_id
GROUP BY c.country
