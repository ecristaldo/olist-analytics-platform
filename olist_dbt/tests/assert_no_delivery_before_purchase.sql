-- An order cannot reach the customer before it was placed. Returns the offending orders.
--
-- Olist data has oddities, so this may fail. If it does: look at the rows first, then decide
-- whether it is an error (fix it) or a known trait of the dataset (then add a config block
-- with severity='warn' as the first line of this file, and write the reason here). Do not
-- hide it before looking.
--
-- Wall-clock times are compared on purpose. stg_olist__orders builds purchased_at as a true
-- instant (Sao Paulo time), but delivered_customer_at is a plain cast, so its clock reading is
-- the Sao Paulo wall time labelled as UTC. Comparing the two directly would be 3 hours off.

select
    order_id,
    order_status,
    purchased_at,
    delivered_customer_at
from {{ ref('stg_olist__orders') }}
where delivered_customer_at is not null
  and delivered_customer_at < purchased_at
