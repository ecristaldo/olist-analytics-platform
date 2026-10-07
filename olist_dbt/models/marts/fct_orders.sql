-- One row per order: the order itself, what was bought and paid (BRL), and the
-- same revenue in GBP at the exchange rate of the day the order was placed.
--
-- Joins are LEFT JOINs from the orders side, so no order is ever dropped:
--   * no items    -> items / freight / gross revenue (BRL and GBP) are NULL, item_count = 0
--   * no payments -> paid_brl and main_payment_type are NULL, payment_count = 0
-- (sums over nothing are NULL, counts over nothing are 0)
--
-- FX: purchased_at is an instant (UTC); the rate is looked up for the calendar day it was
-- in São Paulo, because that is the day the customer actually placed the order.
-- GBP is rounded once, in the last step, never in the middle of a calculation.

with orders as (

    select
        order_id,
        customer_id,
        order_status,
        purchased_at,
        date(purchased_at, 'America/Sao_Paulo') as purchase_date
    from {{ ref('stg_olist__orders') }}

),

items as (

    select * from {{ ref('int_order_items__by_order') }}

),

payments as (

    select * from {{ ref('int_order_payments__by_order') }}

),

fx as (

    select * from {{ ref('int_fx__rates_daily') }}

),

joined as (

    select
        orders.order_id,
        orders.customer_id,
        orders.order_status,
        orders.purchased_at,
        orders.purchase_date,

        coalesce(items.item_count, 0) as item_count,
        items.items_value as items_value_brl,
        items.freight_value as freight_value_brl,
        items.items_value + items.freight_value as gross_revenue_brl,

        coalesce(payments.payment_count, 0) as payment_count,
        payments.main_payment_type,
        payments.total_paid as paid_brl,

        fx.gbp_per_brl,
        fx.is_forward_filled as is_fx_forward_filled

    from orders
    left join items
        on items.order_id = orders.order_id
    left join payments
        on payments.order_id = orders.order_id
    left join fx
        on fx.rate_date = orders.purchase_date

)

select
    order_id,
    customer_id,
    order_status,
    purchased_at,
    items_value_brl,
    freight_value_brl,
    gross_revenue_brl,
    paid_brl,
    gbp_per_brl,
    round(gross_revenue_brl * gbp_per_brl, 2) as gross_revenue_gbp,
    is_fx_forward_filled,
    purchase_date,
    item_count,
    payment_count,
    main_payment_type
from joined
