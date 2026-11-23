SELECT
  c.country,
  SUM(o.amount) AS revenue,
  {{ m.price_bucket('SUM(o.amount)', 100) }} AS bucket
FROM {{ ref('stg_orders') }} AS o
JOIN {{ ref('stg_customers') }} AS c ON o.customer_id = c.customer_id
WHERE c.country = '{{ var('region', 'US') }}'
GROUP BY c.country
