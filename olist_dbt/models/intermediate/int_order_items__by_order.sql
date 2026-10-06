-- One row per order: what was bought and the freight on it.
-- Not every order has items (e.g. cancelled / unavailable ones), so join to this
-- model with a LEFT JOIN from the orders side.

with order_items as (

    select
        order_id,
        item_price,
        freight_value
    from {{ ref('stg_olist__order_items') }}

),

by_order as (

    select
        order_id,
        count(*) as item_count,
        sum(item_price) as items_value,
        sum(freight_value) as freight_value
    from order_items
    group by order_id

)

select * from by_order
