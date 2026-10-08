select 1
from (select countif(payment_installments > 1) as n
      from {{ ref('stg_olist__order_payments') }})
where n = 0