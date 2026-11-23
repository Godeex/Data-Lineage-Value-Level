SELECT
  c.customer_id,
  c.name,
  SUM(o.amount) AS revenue,
  {{ m.price_bucket('SUM(o.amount)', 100) }} AS bucket
FROM {{ ref('stg_orders') }} AS o
JOIN {{ ref('stg_customers') }} AS c
  ON o.customer_id = c.customer_id
{% if var('include_refunds') %}
WHERE o.refunded = 0
{% endif %}
GROUP BY c.customer_id, c.name
