SELECT
  c.country,
  SUM(o.amount * (1 + COALESCE(t.rate, 0))) AS revenue
FROM {{ ref('stg_orders') }} AS o
JOIN {{ ref('stg_customers') }} AS c ON o.customer_id = c.customer_id
LEFT JOIN raw_tax AS t ON c.country = t.country
{% if var('include_tax') %}
GROUP BY c.country
{% endif %}
