{{ config(severity='error', warn_if='>0', error_if='>350') }}

-- Known data issue, kept visible on purpose: some orders were paid a different amount than
-- items + freight (303 orders when this was written).
--   1 to 350 rows -> warning on every build, the build goes on (the known 303 fit here)
--   more than 350 -> error, the build stops: something new broke
-- Thresholds are for the number of ROWS returned, one per mismatching order. If the data
-- is reloaded and the known count changes for a good reason, move 350 along with it.
--
-- Only orders that have both items and payments are compared. Orders with no items or no
-- payments are a different, separate question (see the not_null / row-count tests).
-- Same rule as the original reconciliation query: abs(items + freight - paid) > 0.01.

select
    order_id,
    order_status,
    gross_revenue_brl,
    paid_brl,
    paid_brl - gross_revenue_brl as difference
from {{ ref('fct_orders') }}
where item_count > 0
  and payment_count > 0
  and abs(gross_revenue_brl - paid_brl) > 0.01
